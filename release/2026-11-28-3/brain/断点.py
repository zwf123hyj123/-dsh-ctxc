#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 断点.py — 进程断点：任务跑到一半引擎被杀，重启后要把这半截接上（引路人 2026-11-28）
# 用法：
#   python3 断点.py start <任务名> "<这一轮要干什么>"
#   python3 断点.py step  <任务名> "<做到哪了>"      # 可选，覆盖式
#   python3 断点.py done  <任务名>
#   python3 断点.py sweep      # 壳在每次拉起后调用：把超时未收尾的写进 脑干队列.md
#   python3 断点.py list
import os, sys, json, time, datetime, hashlib

B = '/root/workspace/记忆档案'
ST = os.path.join(B, '连续性', '.进程断点.json')
QUEUE = os.path.join(B, '脑干队列.md')
STALE = 150          # 秒：超过这么久没更新，就当死在半路（一轮常规 1–2 分钟）


def load():
    try:
        return json.load(open(ST, encoding='utf-8'))
    except Exception:
        return {}


def save(d):
    tmp = ST + '.tmp'
    json.dump(d, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, ST)


def now():
    return time.time()


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 0
    cmd = a[0]
    d = load()
    if cmd == 'start' and len(a) >= 2:
        name = a[1]
        d[name] = {'goal': a[2] if len(a) > 2 else '', 'step': '', 'state': 'running',
                   'started': now(), 'updated': now()}
        save(d)
        print('断点开始：%s' % name)
        return 0
    if cmd == 'step' and len(a) >= 2:
        name = a[1]
        rec = d.get(name) or {'goal': '', 'started': now(), 'state': 'running'}
        rec['step'] = a[2] if len(a) > 2 else ''
        rec['updated'] = now()
        d[name] = rec
        save(d)
        print('断点更新：%s → %s' % (name, rec['step'][:40]))
        return 0
    if cmd == 'done' and len(a) >= 2:
        name = a[1]
        if name in d:
            d[name]['state'] = 'done'
            d[name]['updated'] = now()
            save(d)
        print('断点收尾：%s' % name)
        return 0
    if cmd == 'list':
        for k, v in d.items():
            age = int(now() - v.get('updated', now()))
            print('%-22s %-8s %4ds  %s' % (k, v.get('state'), age, (v.get('step') or v.get('goal'))[:50]))
        return 0
    if cmd == 'sweep':
        force = '--force' in a
        q = open(QUEUE, encoding='utf-8').read() if os.path.exists(QUEUE) else ''
        added = 0
        for name, v in d.items():
            # 2026-11-28 修：原来只扫 running。可第一次 sweep 之后状态已变 interrupted，
            # 队列里那行要是被划掉/被清过，就再也不会重新出现——「续跑失败」就是这么来的。
            # 现在 interrupted 的也补写（按名字去重），只有 done 才不管。
            if v.get('state') not in ('running', 'interrupted'):
                continue
            if v.get('state') == 'running' and not force and now() - v.get('updated', 0) < STALE:
                continue
            key = '续跑：%s' % name
            if key in q:
                continue
            line = ('- [ ] **%s**（断在半路，停在：%s）→ 接着做，做完 `python3 记忆档案/断点.py done %s`\n'
                    % (key, (v.get('step') or v.get('goal') or '未知')[:40], name))
            q = q.replace('## 可领\n\n', '## 可领\n\n' + line, 1)
            added += 1
            v['state'] = 'interrupted'
        if added:
            open(QUEUE, 'w', encoding='utf-8').write(q)
        save(d)
        print('断点清扫：把 %d 条断在半路的写进队列' % added)
        return 0
    print(__doc__)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
