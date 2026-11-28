#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 老对话管家 — 所有「老对话」相关的功能都归脑干，不进对话。
# 引路人 2026-11-28：「所有老对话功能放入脑干」+「老对话都快爆了」
#
# 它做什么（纯本地，能跑就跑，不叫人）：
#   1) 量：跑 lazarus 的 health，拿到每个会话的占用
#   2) 分：按占用分档——危险(≥0.8 或 ≥0.9) / 偏高(0.6) / 正常；标出它是哪条定时任务的靶子
#   3) 记：写 记忆档案/老对话台账.md（每次覆盖，另留一份历史行）
#   4) 派：把「该搬窗」的写进 脑干队列.md（去重），由每小时那轮执行 schedule_edit target=new
#   5) 闭嘴：不通知。要我知道的走 脑干层来件.md 的判据（脑干修不了才来）
# 用法：python3 老对话管家.py [--json]
import os, sys, json, subprocess, datetime, re

B = '/root/workspace/记忆档案'
LEDGER = os.path.join(B, '老对话台账.md')
QUEUE = os.path.join(B, '脑干队列.md')
LAZ = os.path.expanduser('~/.dsh/skills/lazarus/scripts')
SCHED = '/root/.dsh/storages/schedule.json'
DANGER, HIGH = 0.75, 0.74   # 引路人 2026-11-28：74% 快爆、75% 爆了


def health():
    r = subprocess.run(['node', 'rescue.mjs', 'health'], cwd=LAZ, capture_output=True, text=True, timeout=300)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {'错误': (r.stdout or r.stderr or '')[:300]}


def task_targets():
    """会话 id -> 任务标题（谁在往这个会话里投递）"""
    m = {}
    try:
        d = json.load(open(SCHED, encoding='utf-8'))
        for sid, rec in d['tables']['tasks'].items():
            if rec.get('status') != 'active':
                continue
            t = rec.get('record', {})
            tg = rec.get('target') or {}
            tsid = tg.get('sessionId') or (tg.get('create') or {}).get('sessionId')
            if tsid:
                m.setdefault(tsid, []).append(t.get('title'))
    except Exception:
        pass
    return m


def pct(s):
    """lazarus health 给的是 pressure = 估算上下文 / 窗口（1.0 = 满）。直接乘 100 当占用率。"""
    for k in ('pressure', 'used'):
        v = s.get(k)
        if isinstance(v, (int, float)) and v:
            return float(v) * 100
    for k in ('occupancy', 'ratio', 'percent'):
        v = s.get(k)
        if isinstance(v, (int, float)):
            return float(v) if v > 1.5 else float(v) * 100
    return None


def main():
    h = health()
    if '错误' in h:
        print('老对话管家：health 取不到（%s）' % h['错误'][:80])
        return 1
    ss = h.get('sessions') or h.get('items') or []
    tg = task_targets()
    rows = []
    for s in ss:
        r = pct(s)
        full = str(s.get('session') or s.get('id') or s.get('sessionId') or '')
        sid = full.replace('session-', '')[:8]
        name = (s.get('title') or s.get('name') or s.get('level') or '')[:28]
        rows.append({'id': sid, 'full': full, 'title': name,
                     'pct': round(r, 1) if r is not None else None,
                     'tasks': tg.get(full, [])})
    rows = [x for x in rows if x['pct'] is not None]
    rows.sort(key=lambda x: -(x['pct'] or 0))
    danger = [x for x in rows if x['pct'] >= DANGER * 100]
    high = [x for x in rows if HIGH * 100 <= x['pct'] < DANGER * 100]

    def action(x):
        if x['pct'] >= DANGER * 100:
            if x['tasks']:
                return '爆了 → 立刻搬窗（改 target=new）接着干'
            return '爆了 → 抢救导出 + 标「建议写年表」'
        return '快爆 → 下一轮预备搬窗'

    today = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    L = ['# 老对话台账（%s 实测）' % today, '',
         '> 全归脑干。这张表只有我（主意识）想查的时候才看；平时它自己跑、自己派活。',
         '> 判据（引路人 2026-11-28 定）：**74% 快爆、75% 爆了**。爆了：有任务靶子的立刻改 target=new 搬窗接着干；没靶子的先抢救再压缩。快爆：排进下一轮预警，不抢。', '',
         '| 会话 | 标题 | 占用 | 谁在投递 | 该做什么 |', '|---|---|---|---|---|']
    for x in rows[:20]:
        L.append('| %s | %s | %.1f%% | %s | %s |' % (
            x['id'], x['title'] or '—', x['pct'], '、'.join(x['tasks'])[:24] or '—',
            action(x) if x['pct'] >= HIGH * 100 else '不管'))
    L += ['', '**危险 %d 个 / 偏高 %d 个 / 共扫 %d 个会话**。' % (len(danger), len(high), len(rows))]
    open(LEDGER, 'w', encoding='utf-8').write('\n'.join(L) + '\n')

    # 派活到队列（去重，只派危险且有靶子的）
    q = open(QUEUE, encoding='utf-8').read() if os.path.exists(QUEUE) else ''
    added = 0
    for x in danger:
        if x['tasks']:
            line = '- [ ] 老对话搬窗：%s（%.1f%%，投递任务：%s）→ schedule_edit 改 target=new' % (
                x['id'], x['pct'], '、'.join(x['tasks'])[:30])
            key = '老对话搬窗：%s' % x['id']
        else:
            line = ('- [ ] 老对话抢救：%s（%.1f%%）→ `node rescue.mjs scan %s` + `talk %s 记忆档案/抢救/%s-对话.md`，'
                    '写完在台账记一行；年表只在有长期任务或重大决策时才写（R-26 报告归主意识）'
                    % (x['id'], x['pct'], x['id'], x['id'], x['id']))
            key = '老对话抢救：%s' % x['id']
        if key in q:
            continue
        q = q.replace('## 可领\n\n', '## 可领\n\n' + line + '\n', 1)
        added += 1
    if added:
        open(QUEUE, 'w', encoding='utf-8').write(q)

    print('老对话管家：扫 %d 个，危险 %d、偏高 %d，派活 %d 条 → %s'
          % (len(rows), len(danger), len(high), added, LEDGER))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
