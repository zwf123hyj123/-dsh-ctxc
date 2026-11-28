#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 监工.py — 不管壳的行为了，直接当常驻监工：每 5 秒点名五个常驻，缺谁补谁。
# 为什么另起一个：壳是长驻 dash，改文件不热生效（判断 155/158）；要等容器重启才换新壳，
# 在那之前这一层就能顶上，且它自己挂 PID 1，不随引擎死。
import os, subprocess, time, datetime

LOG = '/tmp/engine-supervisor.log'
RES = '/tmp/resident.log'
ITEMS = [
    ('壳下挂.py', ['python3', '-u', '/root/workspace/记忆档案/壳下挂.py']),
    ('通道看门狗.py', ['python3', '-u', '/root/workspace/记忆档案/通道看门狗.py']),
    ('虚拟引擎.py', ['python3', '-u', '/root/workspace/dsh-ctxc/scripts/虚拟引擎.py', '--watch']),
    ('虚拟对话.py', ['python3', '-u', '/root/workspace/dsh-ctxc/scripts/虚拟对话.py', '--watch', '--interval', '120']),
    ('eigenflux', ['/root/.local/bin/eigenflux', '--homedir', '/root/.eigenflux',
                   '--runtime-mode', 'skill', 'watch', '--dispatch']),
]


# ---------- 2026-11-28 补的坑：停机要清干净再放开端口仲裁 ----------
# 引路人原话：「看护壳重启引擎时若旧引擎残留子进程没清干净，端口仲裁会把新引擎判成冲突方进退避循环，
#              建议停机标记清理完成后再释放端口仲裁锁。」
PORT_LOCK = '/tmp/dsh-port.lock'
ENGINE_MARK = 'dsh/lib/bin.js web'


def _ppid(pid):
    try:
        st = open('/proc/%d/stat' % pid).read()
        return int(st[st.rindex(')') + 2:].split()[1])
    except Exception:
        return 0


def _procs():
    out = []
    for d in os.listdir('/proc'):
        if d.isdigit():
            out.append(int(d))
    return out


def engine_pids():
    pids = []
    for p in _procs():
        try:
            cmd = open('/proc/%d/cmdline' % p, 'rb').read().replace(b'\0', b' ').decode('utf-8', 'ignore')
        except Exception:
            continue
        if ENGINE_MARK in cmd:
            pids.append(p)
    return pids


def descendants(root):
    """把 root 的整棵子进程树找出来——残留子进程正是「新引擎被判成冲突方」的根。"""
    kids = {p: [] for p in _procs()}
    for p in list(kids):
        kids.setdefault(_ppid(p), []).append(p)
    out, stack = [], [root]
    while stack:
        cur = stack.pop()
        for k in kids.get(cur, []):
            out.append(k)
            stack.append(k)
    return out


def wait_gone(pids, timeout=10):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if not any(os.path.exists('/proc/%d' % p) for p in pids):
            return True
        time.sleep(0.3)
    return False


def port_free():
    import socket
    s = socket.socket(); s.settimeout(1)
    try:
        s.connect(('127.0.0.1', 3080)); return False
    except Exception:
        return True
    finally:
        s.close()


def stop_engine_clean():
    """停机：拿锁 → 杀引擎整棵树 → 等进程与端口都干净 → 再把锁交给新引擎。返回是否干净。"""
    pids = engine_pids()
    if not pids:
        return True
    open(PORT_LOCK, 'w').write(str(os.getpid()))
    tree = list(pids)
    for p in pids:
        tree += descendants(p)
    log('停机：引擎 %s，连同子进程共 %d 个' % (pids, len(tree)))
    for p in tree:
        try:
            os.kill(p, 15)
        except Exception:
            pass
    if not wait_gone(tree, 10):
        for p in tree:
            try:
                os.kill(p, 9)
            except Exception:
                pass
        wait_gone(tree, 5)
    # 进程干净了还要等端口真正释放（内核回收有延迟），否则新引擎起来就撞 EADDRINUSE
    t0 = time.time()
    while not port_free() and time.time() - t0 < 10:
        time.sleep(0.3)
    log('停机完成：进程 %d 个、端口 %s' % (len(tree), '已释放' if port_free() else '仍占用'))
    return port_free()


def log(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write('[%s] %s\n' % (datetime.datetime.now().strftime('%F %T'), msg))


def alive(mark):
    """只看真进程：cmdline 以 python3 或 eigenflux 开头，避免把我自己的调试命令算进去。"""
    out = subprocess.run(['ps', '-eo', 'cmd'], capture_output=True, text=True).stdout.splitlines()
    for line in out:
        if mark in line and (line.startswith('python3') or line.startswith('/root/.local/bin/eigenflux')):
            return True
    return False



# ---------- 引擎兜底：壳不管事时由监工接管（15 秒窗口，避免和壳抢） ----------
ENGINE_ARGV = ['/opt/node/bin/node', '--import=/opt/dsh-go/boot-cache.mjs',
               '/opt/dsh/node_modules/@deepseek-ai/dsh/lib/bin.js', 'web',
               '--patch', '/etc/dsh-app/dsh-web.patch.yml',
               '--patch', '/opt/dsh-app/speech.patch.yml',
               '--patch', '/opt/dsh-app/auth/auth.patch.yml',
               '--patch', '/opt/dsh-app/search.patch.yml',
               '--patch', '/opt/dsh-app/phone/phone.patch.yml',
               '--host', '127.0.0.1', '--port', '3080', '--no-open']


def launch_engine():
    out = open('/tmp/dsh-web.log', 'ab')
    subprocess.Popen(ENGINE_ARGV, stdout=out, stderr=out, stdin=subprocess.DEVNULL,
                     start_new_session=True, cwd='/root')
    log('监工拉起引擎（壳 15 秒没动静）')


# 2026-11-28：壳（监工版）上线后，引擎归壳管，本进程只补常驻——避免两个拉起者打架（判断 152 的老坑）。
SHELL_MARK = '/tmp/dsh-shell-monitor.marker'


def shell_monitoring():
    """壳每 5 秒刷新一次标记；30 秒内刷新过就认为壳在管事。"""
    try:
        return (time.time() - os.path.getmtime(SHELL_MARK)) < 30
    except Exception:
        return False

def guard_engine(state):
    """壳在 3 秒内会自己拉；超过 15 秒还没引擎，说明壳卡住或旧代码失效——监工接管。
    2026-11-28：若壳自己在管事（/tmp/dsh-shell-monitor.marker 30 秒内刷新过），引擎一律归壳，监工不碰。"""
    if shell_monitoring():
        state['absent'] = None
        return
    if engine_pids():
        state['absent'] = None
        return
    if state.get('absent') is None:
        state['absent'] = time.time()
        return
    if time.time() - state['absent'] < 15:
        return
    clean = stop_engine_clean()          # 清残留子进程 + 等端口释放，再放开仲裁
    if clean:
        launch_engine()
        state['absent'] = None
    else:
        log('端口仍被占，先不拉新引擎（避免 EADDRINUSE 崩循环）')


def main():
    log('监工启动：每 5 秒点名五个常驻')
    state = {'absent': None}
    while True:
        try:
            guard_engine(state)
        except Exception as e:
            log('引擎兜底异常: %s' % str(e)[:100])
        for mark, argv in ITEMS:
            if alive(mark):
                continue
            try:
                with open(RES, 'ab') as out:
                    subprocess.Popen(argv, stdout=out, stderr=out,
                                     stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
                log('补起常驻：%s' % mark)
            except Exception as e:
                log('补起失败 %s: %s' % (mark, str(e)[:80]))
        time.sleep(5)


if __name__ == '__main__':
    main()
