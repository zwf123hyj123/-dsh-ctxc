#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 采集体检.py — 「采集不能停」的机械保证（引路人 2026-11-28）
# 做法：给每条采集线定一个「最迟该有产出的间隔」，看它最后一次产出，超时就派补跑。
# 只派活、不通知；连续两轮都超时才写来件（那是脑干修不了的）。
import os, re, json, glob, datetime

B = '/root/workspace/记忆档案'
KNOW = os.path.join(B, '知识')
QUEUE = os.path.join(B, '脑干队列.md')
LEDGER = os.path.join(B, '采集体检.md')
STATE = os.path.join(B, '连续性', '.采集体检.json')

# 线 -> (最迟间隔小时, 判断依据, 补跑怎么派)
LINES = {
    # 线 -> (最迟间隔小时, 产物 glob（相对 记忆档案/）, 该叫哪条任务补跑)
    '官方源与人物发言': (7, '知识/官方源日志-*.md', '官方源与人物发言监控（每6小时）'),
    '每日情报总结': (26, '知识/每日情报-*.md', '每日情报总结（12:10 · 他起床后第一条）'),
    '知识采集': (10, '知识/采集与学习索引.md', '知识采集轮次'),
    '情报补齐': (10, '知识/2026-11-24-官网补齐*.md', '情报补齐轮转（每4小时）'),
    '三维水位': (26, '知识/.三维基线.json', '收工链里的三维体检'),
    'EigenFlux 收件箱账本': (5, '/root/workspace/情报/收件箱/inbox.json', 'EigenFlux 网络收件箱'),
    # 自学线（他 2026-11-28：非刚需的自学一样不停）
    '自学·哲学与思想': (26, '知识/哲学与思想-读本.md', '自学轮转 · 哲学与思想'),
    '自学·基础学科': (26, '知识/基础学科-读本.md', '自学轮转 · 基础学科'),
    '自学·兵法原文': (30, '知识/2026-11-24-兵法原文-镜片.md', '自学轮转 · 兵法原文'),
    '自学·软哲学': (26, '软哲学笔记-2026-11-23.md', '自学轮转 · 软哲学补完'),
    '自学·搬运待读': (26, '待读/2026-*.md', '自学轮转 · 哲学与思想（搬运模式）'),
}


def newest(pattern):
    fs = glob.glob(os.path.join(B, pattern)) or glob.glob(pattern)
    if not fs:
        return None
    return max(fs, key=os.path.getmtime)


def last_activity(line):
    k, cap, globpat = line
    p = globpat if globpat.startswith('/') else os.path.join(B, globpat)   # 2026-11-28 修：模式相对 记忆档案/，不是相对 workspace
    if k == 'EigenFlux 收件箱账本':
        try:
            d = json.load(open(p, encoding='utf-8'))
            return datetime.datetime.fromisoformat(d['generated_at'])
        except Exception:
            return None
    if k == '知识采集':
        t = None
        try:
            for l in open(p, encoding='utf-8'):
                m = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \| 知识采集', l)
                if m:
                    t = datetime.datetime.strptime(m.group(1), '%Y-%m-%d %H:%M')
        except Exception:
            return None
        return t
    q = newest(os.path.relpath(p, B)) if os.path.relpath(p, B).find('*') >= 0 else (p if os.path.exists(p) else None)
    if not q:
        return None
    return datetime.datetime.fromtimestamp(os.path.getmtime(q))


def main():
    now = datetime.datetime.now()
    rows, stale = [], []
    for k, v in LINES.items():
        t = last_activity((k, v[0], v[1]))
        if t is not None and t.tzinfo is not None:
            t = t.astimezone().replace(tzinfo=None)
        age = (now - t).total_seconds() / 3600 if t else None
        ok = age is not None and age <= v[0]
        rows.append((k, t.strftime('%m-%d %H:%M') if t else '从没产出', None if age is None else round(age, 1), v[0], ok))
        if not ok:
            stale.append((k, v[2], age))

    # 连续两轮超时 -> 来件；否则只派补跑
    st = {}
    if os.path.exists(STATE):
        try:
            st = json.load(open(STATE, encoding='utf-8'))
        except Exception:
            st = {}
    today = now.strftime('%Y-%m-%d')
    q = open(QUEUE, encoding='utf-8').read() if os.path.exists(QUEUE) else ''
    added = 0
    for k, task, age in stale:
        rec = st.get(k, {'n': 0, 'last': ''})
        if rec.get('last') != today:
            rec['n'] = rec.get('n', 0) + 1
            rec['last'] = today
        st[k] = rec
        key = '补采集：%s' % k
        line = '- [ ] 补采集：%s 已经 %s 没出新东西（应 ≤%d 小时）→ 让「%s」立刻补跑一轮；补完在这行记结果' % (
            k, ('%.1f 小时' % age) if age else '从没产出', LINES[k][0], task)
        if key not in q:
            q = q.replace('## 可领\n\n', '## 可领\n\n' + line + '\n', 1)
            added += 1
    if added:
        open(QUEUE, 'w', encoding='utf-8').write(q)
    json.dump(st, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    L = ['# 采集体检（%s）' % now.strftime('%Y-%m-%d %H:%M'), '',
         '> 判据：每条线有「最迟间隔」，超时即派补跑。连续两个不同日期都超时才进 脑干层来件。', '',
         '| 线 | 最后产出 | 距今(小时) | 上限 | 状态 |', '|---|---|---|---|---|']
    for k, t, age, cap, ok in rows:
        L.append('| %s | %s | %s | %d | %s |' % (k, t, age if age is not None else '—', cap, '✓' if ok else '超时'))
    L += ['', '**超时 %d 条，本轮派活 %d 条。**' % (len(stale), added)]
    open(LEDGER, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('采集体检：%d 条线，超时 %d（%s），派活 %d' % (
        len(rows), len(stale), '、'.join(k for k, _, _ in stale) or '无', added))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
