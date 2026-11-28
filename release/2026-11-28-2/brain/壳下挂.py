#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 壳下挂.py — 挂在壳下面的伴生脚本（引路人 2026-11-28 第三步）：
#   引擎回来后，把断点文件里的东西接回对话——不是只排队等下一小时，
#   而是在调度表里插一条一次性任务（COUNT=1，投给新会话），让它立刻接着干。
# 用法：python3 壳下挂.py --once   # 单次
#       python3 壳下挂.py          # 常驻，每 5 秒看一次
import os, sys, json, glob, time, datetime, shutil, uuid

B = '/root/workspace/记忆档案'
SIG = os.path.join(B, '连续性', '.停止广播.json')
ST = os.path.join(B, '连续性', '.进程断点.json')
MARK = os.path.join(B, '连续性', '.下挂已接.json')
SCHED = '/root/.dsh/storages/schedule.json'
QUEUE = os.path.join(B, '脑干队列.md')
LOG = '/tmp/壳下挂.log'


def log(m):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write('[%s] %s\n' % (datetime.datetime.now().strftime('%H:%M:%S'), m))


def engine_up():
    import urllib.request
    try:
        urllib.request.urlopen('http://127.0.0.1:3080/', timeout=2).read(32)
        return True
    except Exception:
        # 401 也算活着（urllib 会抛 HTTPError）
        import urllib.error
        try:
            urllib.request.urlopen('http://127.0.0.1:3080/', timeout=2)
        except urllib.error.HTTPError:
            return True
        except Exception:
            return False


def pending():
    try:
        d = json.load(open(ST, encoding='utf-8'))
    except Exception:
        return []
    return [(k, v) for k, v in d.items() if v.get('state') in ('running', 'interrupted')]


BOOT = '/root/.dsh/dsh-go/auto-continue/boot.json'


def inject(items):
    """不伪造调度记录（实测外部写入引擎不认，投递永远 0）。
    改成写「开机票」：下一轮自我唤醒读到就会立刻接着干。"""
    body = [{'任务': k, '停在': (v.get('step') or v.get('goal') or '')[:60]} for k, v in items]
    try:
        old = json.load(open(BOOT, encoding='utf-8'))
    except Exception:
        old = {}
    old.update({'consumed': False, 'reason': '引擎重启续跑', 'resume': body,
                'set_at': datetime.datetime.now().strftime('%F %T')})
    os.makedirs(os.path.dirname(BOOT), exist_ok=True)
    json.dump(old, open(BOOT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    log('已写开机票（%d 条断点），下一轮自我唤醒会接着干' % len(body))
    return True


def run_once(pre=False):
    sig = None
    try:
        sig = json.load(open(SIG, encoding='utf-8'))
    except Exception:
        pass
    items = pending()
    if not items:
        return
    if not pre and not engine_up():
        return
    try:
        done = json.load(open(MARK, encoding='utf-8'))
    except Exception:
        done = {}
    key = str(int(sig.get('ts', 0))) if sig else 'manual'
    if done.get('key') == key:
        return
    if inject(items):
        json.dump({'key': key, 'at': datetime.datetime.now().strftime('%F %T')},
                  open(MARK, 'w', encoding='utf-8'), ensure_ascii=False)
        # 顺手把队列里的续跑条目补上，两边对得上
        q = open(QUEUE, encoding='utf-8').read() if os.path.exists(QUEUE) else ''
        for k, v in items:
            if '续跑：%s' % k in q:
                continue
            q = q.replace('## 可领\n\n', '## 可领\n\n- [ ] **续跑：%s**（停在：%s）→ 接着做，做完 `断点.py done %s`\n'
                          % (k, (v.get('step') or v.get('goal') or '')[:40], k), 1)
        open(QUEUE, 'w', encoding='utf-8').write(q)


KEEP = [
    # 2026-11-28：「干说不改」的补救——监工也要被点名，否则它自己没了没人知道
    ('监工.py', ['python3', '-u', '/root/workspace/记忆档案/监工.py']),
    ('虚拟对话.py', ['python3', '-u', '/root/workspace/dsh-ctxc/scripts/虚拟对话.py', '--watch', '--interval', '120']),
    ('虚拟引擎.py', ['python3', '-u', '/root/workspace/dsh-ctxc/scripts/虚拟引擎.py', '--watch']),
    ('通道看门狗.py', ['python3', '-u', '/root/workspace/记忆档案/通道看门狗.py']),
    ('eigenflux watch', ['/root/.local/bin/eigenflux', '--homedir', '/root/.eigenflux',
                         '--runtime-mode', 'skill', 'watch', '--dispatch']),
]


def keepalive():
    """2026-11-28：挂 PID 1 只保证「不随引擎死」，不保证「死了会回来」。
    这里补上监督：缺谁起谁，一分钟看一次（壳下挂自己挂在 PID 1）。"""
    import subprocess as sp
    out = sp.run(['ps', '-eo', 'cmd'], capture_output=True, text=True).stdout.split('\n')
    # 只认「以 python3/eigenflux 开头」的行，否则 grep/调试命令里带同名串会被误判成在跑（判断 160）
    lines = [l.strip() for l in out if l.strip().startswith(('python3', '/root/.local/bin/eigenflux'))]
    for name, argv in KEEP:
        if any(name in l for l in lines):
            continue
        try:
            sp.Popen(argv, stdout=open('/tmp/常驻保活.log', 'ab'), stderr=sp.STDOUT,
                     stdin=sp.DEVNULL, start_new_session=True)
            log('常驻补拉：%s' % name)
        except Exception as e:
            log('常驻补拉失败 %s：%s' % (name, str(e)[:60]))


def main():
    if '--pre' in sys.argv:
        # 引擎还没起时调用：只做注入（调度表只在启动时读一次，注入必须在拉起之前）
        run_once(pre=True)
        print('下挂预注入完成')
        return 0
    if '--once' in sys.argv:
        run_once()
        print('下挂单次完成，日志 /tmp/壳下挂.log')
        return 0
    log('壳下挂启动（每 5 秒一轮，60 秒一次常驻保活）')
    _t = 0
    while True:
        try:
            run_once()
            _t += 1
            if _t % 12 == 0:
                keepalive()
        except Exception as e:
            log('轮次异常: %s' % str(e)[:120])
        time.sleep(5)


if __name__ == '__main__':
    raise SystemExit(main())
