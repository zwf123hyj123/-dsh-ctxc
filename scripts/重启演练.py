#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重启演练：在隔离环境里把 hot_restart 整条链路真跑一遍，不动生产引擎。

为什么要有它：2026-11-26 热重启把执行者自己杀掉了，事后只能靠"没有 last-restart.json"倒推。
以后再改重启逻辑，需要有办法**不打断使用者的会话**就验证：预检 → 找主进程 → SIGTERM → 等端口释放 →
拉起 → 等就绪 → 自验 → 落账。

做法（隔离三件套）：
  1. 替身"引擎"：`python3 -m http.server <临时端口>`，只在本机 127.0.0.1；
  2. 把 LAUNCH / PORTS / STATE_DIR / find_main_pids 指到替身，绝不碰 3080 与真实 engine-standby；
  3. 跳过 handover_note（不写真镜像）与 ensure_local_model（与重启本身无关的旁路），其余步骤原样执行。

判据（这次演练算不算过）：
  A. hot_restart() 返回 True；
  B. 隔离目录里的 last-restart.json 存在、ok=true、engine_pids 非空、checks.端口通=true；
  C. 演练结束后替身进程数为 0（没留垃圾），且真实 3080 的引擎 pid 未变。

用法：python3 重启演练.py
"""
import importlib.util, json, os, shutil, subprocess, sys, time

SRC = '/root/workspace/dsh-ctxc/scripts/虚拟引擎.py'
DRILL_PORT = 3099
DRILL_DIR = '/tmp/ve-drill'


def load_module():
    spec = importlib.util.spec_from_file_location('ve_drill', SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)      # 注意：main() 只在 __main__ 下跑，import 无副作用
    return m


def real_engine_pids():
    out = subprocess.run(['ps', '-eo', 'pid,args'], capture_output=True, text=True).stdout
    pids = []
    for line in out.splitlines():
        if 'bin.js web' in line and '--port 3080' in line and 'grep' not in line:
            try:
                pids.append(int(line.split()[0]))
            except Exception:
                pass
    return pids


def drill_pids():
    out = subprocess.run(['ps', '-eo', 'pid,args'], capture_output=True, text=True).stdout
    tag = 'http.server %d' % DRILL_PORT
    pids = []
    for line in out.splitlines():
        if tag in line and 'grep' not in line:
            try:
                pids.append(int(line.split()[0]))
            except Exception:
                pass
    return pids


def main():
    ve = load_module()
    before = real_engine_pids()
    print('真引擎 pid（演练前后应一致）：', before)

    shutil.rmtree(DRILL_DIR, ignore_errors=True)
    os.makedirs(DRILL_DIR, mode=0o700, exist_ok=True)

    # —— 隔离：把我当成另一个世界的虚拟引擎 ——
    ve.STATE_DIR = DRILL_DIR
    ve.PORTS = [('drill', DRILL_PORT, '/')]
    ve.LAUNCH = ['python3', '-m', 'http.server', str(DRILL_PORT), '--bind', '127.0.0.1']
    ve.find_main_pids = lambda: drill_pids()
    ve.handover_note = lambda: ve.log('演练：跳过接续包（不写真实镜像）')
    ve.ensure_local_model = lambda: True
    # 演练的替身没有真实配置树，A/B 预验证在这里没有意义（真机由 preview_launch 自己验）
    ve.preview_launch = lambda timeout=60: (True, '演练跳过预验证')

    # 1) 起替身
    out = open(os.path.join(DRILL_DIR, 'drill.log'), 'ab')
    subprocess.Popen(ve.LAUNCH, stdout=out, stderr=out, start_new_session=True, close_fds=True)
    for _ in range(20):
        time.sleep(0.5)
        if drill_pids() and any(ok for _, _, ok in ve.probe()):
            break
    print('替身就绪：', drill_pids(), '端口通:', any(ok for _, _, ok in ve.probe()))

    # 2) 走一遍真实 hot_restart（会 SIGTERM 替身 → 等端口释放 → 拉起 → 自验 → 落账）
    t0 = time.time()
    ok = ve.hot_restart()
    took = round(time.time() - t0, 1)

    # 3) 判据
    res_path = os.path.join(DRILL_DIR, 'last-restart.json')
    res = {}
    try:
        res = json.load(open(res_path, encoding='utf-8'))
    except Exception as e:
        print('读 last-restart.json 失败：', e)

    after_drill = drill_pids()
    after_real = real_engine_pids()
    checks = res.get('checks') or {}
    a = ok is True
    b = bool(res) and res.get('ok') is True and bool(res.get('engine_pids')) and checks.get('端口通') is True
    c = len(after_drill) == 1 and after_real == before
    print('\n— 判据 —')
    print('A hot_restart 返回 True   :', a)
    print('B last-restart 记录完整   :', b, '| 字段:', sorted(res.keys()))
    print('   checks.结论            :', checks.get('结论'))
    print('C 没留垃圾/没碰真引擎     :', c, '| 演练进程', len(after_drill), '| 真引擎', after_real, '(原', before, ')')
    print('用时 %.1fs' % took)

    # 4) 清场：只杀替身（按 pid 精确杀，不用 pkill 通配）
    for pid in after_drill:
        try:
            os.kill(pid, 15)
        except Exception:
            pass
    time.sleep(1)
    left = drill_pids()
    print('清场后残余替身：', left or '0 ✓')
    good = a and b and c and not left
    print('\n演练结论：' + ('通过 ✓' if good else '未通过 ✗'))
    return 0 if good else 1


if __name__ == '__main__':
    sys.exit(main())
