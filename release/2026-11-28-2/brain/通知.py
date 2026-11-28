#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 通知.py — 唯一发通知的出口，懂他的作息。
# 引路人 2026-11-28：「0点到12点我一般不用手机」
# 规则：00:00–11:59 不发（写了也看不到，还可能吵醒人）→ 暂存到 待发通知.md，12 点后一次发出去，合并成一条。
# 用法：
#   python3 通知.py "标题" "正文"          # 自动判断：安静时段就暂存
#   python3 通知.py --flush                # 把暂存的合并发出去（挂在 12:05 的摘要轮）
#   python3 通知.py --now "标题" "正文"     # 紧急：绕过时段（只给「开战级/系统要崩」这类用）
import os, sys, json, datetime

B = '/root/workspace/记忆档案'
QUEUE = os.path.join(B, '待发通知.md')
# 引路人 2026-11-28 两次校准：
#   「0点到12点我一般不用手机」→ 0–12 不主动打扰
#   「6点到12点我有事」      → 0–6 是睡，6–12 是忙，两段不一样：
#       0–6 ：完全静默，叫醒他只有系统要崩/开战级
#       6–12：可以发「一句话要我拍板」的，一天最多 1 条；其余照旧攒
PLAN = '/root/workspace/记忆档案/作息.json'
ASK_COUNT = '/root/workspace/记忆档案/连续性/.今日提问数.json'


def _plan():
    """作息读文件，不写死在代码里——他能随时加窗口，我改数据不改逻辑。"""
    try:
        return json.load(open(PLAN, encoding='utf-8'))
    except Exception:
        return {'sleep': [[0, 360]], 'busy': [[360, 720], [840, 1000]]}


def _in(minute, wins):
    return any(a <= minute < b for a, b in wins)


def tier(now=None):
    n = now or datetime.datetime.now()
    m = n.hour * 60 + n.minute
    p = _plan()
    if _in(m, p.get('sleep', [])):
        return 'sleep'
    if _in(m, p.get('busy', [])):
        return 'busy'
    return 'open'


def quiet(now=None):
    return tier(now) in ('sleep', 'busy')


def _bump_ask():
    today = datetime.date.today().isoformat()
    d = {}
    try:
        d = json.load(open(ASK_COUNT, encoding='utf-8'))
    except Exception:
        d = {}
    if d.get('date') != today:
        d = {'date': today, 'n': 0}
    d['n'] += 1
    json.dump(d, open(ASK_COUNT, 'w', encoding='utf-8'), ensure_ascii=False)
    return d['n']


def _ask_left():
    today = datetime.date.today().isoformat()
    try:
        d = json.load(open(ASK_COUNT, encoding='utf-8'))
        return 1 - d['n'] if d.get('date') == today else 1
    except Exception:
        return 1


def push(title, text):
    old = open(QUEUE, encoding='utf-8').read() if os.path.exists(QUEUE) else '# 待发通知（安静时段暂存）\n\n'
    stamp = datetime.datetime.now().strftime('%m-%d %H:%M')
    old = old.rstrip() + '\n- %s ｜ %s ｜ %s\n' % (stamp, title, text.replace('\n', ' / '))
    open(QUEUE, 'w', encoding='utf-8').write(old)
    print('安静时段：已暂存（%s）' % title)


def send(title, text, via_tool=True):
    """真正发出去。这里是唯一调用手机通知的地方。"""
    try:
        print('NOTIFY\t%s\t%s' % (title, text.replace('\n', ' / ')))
        return True
    except Exception as e:
        print('发送失败：%s' % e)
        return False


def flush():
    if not os.path.exists(QUEUE):
        print('没有暂存通知')
        return 0
    lines = [l.strip('- ').strip() for l in open(QUEUE, encoding='utf-8').read().split('\n') if l.startswith('- ')]
    if not lines:
        print('没有暂存通知')
        return 0
    body = '；'.join(lines[-8:])
    print('FLUSH\t昨夜到上午 %d 条\t%s' % (len(lines), body))
    open(QUEUE, 'w', encoding='utf-8').write('# 待发通知（安静时段暂存）\n\n')
    return len(lines)


if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == '--at' and len(a) > 1:
        hh, _, mm = a[1].partition(':')
        fake = datetime.datetime.now().replace(hour=int(hh), minute=int(mm or 0))
        print('%s → %s' % (a[1], tier(fake)))
        raise SystemExit(0)
    if not a:
        def fmt(w):
            return '、'.join('%d:%02d–%d:%02d' % (a0 // 60, a0 % 60, b0 // 60, b0 % 60) for a0, b0 in w)
        p = _plan()
        t = tier()
        print({'sleep': '现在是睡段【%s】：一律静默，只有要崩/开战才例外' % fmt(p.get('sleep', [])),
               'busy': '现在是忙段【%s】：只发一句话要拍板的，一天 1 条（剩余 %d）'
                       % (fmt(p.get('busy', [])), _ask_left()),
               'open': '现在自由段：正常发'}[t])
    elif a[0] == '--flush':
        flush()
    elif a[0] == '--now' and len(a) >= 3:
        send(a[1], a[2])
    elif len(a) >= 3 and a[0] == '--ask':
        # 6–12 的「一句话要拍板」通道：一天只准 1 条
        if tier() == 'sleep':
            push(a[1], a[2]); print('（0–6 睡着，不叫醒；已暂存）')
        elif tier() == 'busy':
            if _ask_left() > 0:
                _bump_ask(); send(a[1], a[2]); print('（6–12 允许 1 条要拍板的）')
            else:
                push(a[1], a[2]); print('（今天 6–12 的提问额度已用完，暂存到 12 点）')
        else:
            send(a[1], a[2])
    elif len(a) >= 2:
        (push if quiet() else send)(a[0], a[1])
    else:
        print(__doc__)
