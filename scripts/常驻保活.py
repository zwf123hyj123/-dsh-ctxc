#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""常驻保活（维护者 2026-11-25）：虚拟对话镜像 + 虚拟引擎热备，掉了就拉起。

背景：两个 --watch 进程靠 setsid 常驻，App/引擎重启后它们会一起消失。
本脚本由定时任务每小时跑一次：扫 /proc 找活着的 watch，缺哪个补哪个。

判据（怎么算成了）：输出 launched 里的项，脚本跑完后对应 pid 存在且日志有新一轮。

用法：
  python3 常驻保活.py            # 检查 + 补拉
  python3 常驻保活.py --dry      # 只看谁活着
"""
import os, sys, json, glob, time, subprocess

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
KLOG = os.environ.get('KEEPALIVE_LOG', '/tmp/常驻保活.log')  # 与 虚拟对话.py / 虚拟引擎.py 同目录
TARGETS = [
    {'name': '虚拟对话', 'match': '虚拟对话.py --watch', 'cmd': ['python3', '虚拟对话.py', '--watch', '--interval', '120'],
     'out': '/tmp/虚拟对话-watch.log'},
    {'name': '虚拟引擎', 'match': '虚拟引擎.py --watch', 'cmd': ['python3', '虚拟引擎.py', '--watch'],
     'out': '/tmp/虚拟引擎-watch.log'},
]


def note(msg):
    """落盘：谁、什么时候、拉起了什么、被谁叫起来（ppid 是关键证据——
    插件 spawn 的保活是引擎的子进程，手动跑的是终端的子进程）。"""
    try:
        with open(KLOG, 'a', encoding='utf-8') as f:
            f.write('%s pid=%d ppid=%d %s\n' % (
                time.strftime('%Y-%m-%d %H:%M:%S'), os.getpid(), os.getppid(), msg))
    except OSError:
        pass


def running(match):
    """扫 /proc 找命令行含 match 的进程（排除自己与 grep 类）"""
    pids = []
    me = os.getpid()
    for d in glob.glob('/proc/[0-9]*'):
        pid = int(os.path.basename(d))
        if pid == me:
            continue
        try:
            with open(os.path.join(d, 'cmdline'), 'rb') as f:
                cmd = f.read().replace(b'\x00', b' ').decode('utf-8', 'replace')
        except OSError:
            continue
        if match in cmd and '常驻保活' not in cmd and 'grep' not in cmd:
            pids.append(pid)
    return pids


def launch(t):
    os.makedirs(SCRIPTS, exist_ok=True)
    with open(t['out'], 'ab') as out:
        subprocess.Popen(t['cmd'], cwd=SCRIPTS, stdout=out, stderr=out,
                         start_new_session=True, close_fds=True)
    return True


def main():
    dry = '--dry' in sys.argv
    alive, launched, err = {}, [], []
    for t in TARGETS:
        pids = running(t['match'])
        if pids:
            alive[t['name']] = pids
            continue
        if dry:
            alive[t['name']] = []
            continue
        try:
            launch(t)
            launched.append(t['name'])
            note('拉起 %s（cmd=%s）' % (t['name'], ' '.join(t['cmd'])))
        except Exception as e:
            err.append('%s: %s' % (t['name'], str(e)[:80]))
    if launched:
        time.sleep(4)
        for name in launched:
            t = next(x for x in TARGETS if x['name'] == name)
            pids = running(t['match'])
            if not pids:
                err.append('%s 拉起后仍无进程' % name)
            else:
                alive[name] = pids
    note('检查完成：活着=%s 拉起=%s 错误=%s' % (
        ','.join('%s:%s' % (k, v) for k, v in alive.items()) or '-', launched or '-', err or '-'))
    print(json.dumps({'时间': time.strftime('%Y-%m-%d %H:%M:%S'), '活着': alive,
                      '已拉起': launched, '错误': err}, ensure_ascii=False))
    return 0 if not err else 2


if __name__ == '__main__':
    sys.exit(main())
