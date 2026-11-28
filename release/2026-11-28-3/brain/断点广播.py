#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 断点广播.py — 引路人 2026-11-28 定的重启前流程：
#   ① 广播「所有对话停止并各自落断点」 ② 壳换引擎 ③ 下挂脚本把断点接回对话 ④ 刷新后自动干活
# 本脚本只做①：写停止信号 + 把当前所有 running 断点快照成一份人读的断点文件。
# 用法：python3 断点广播.py [原因]
import os, json, time, datetime, glob

B = '/root/workspace/记忆档案'
SIG = os.path.join(B, '连续性', '.停止广播.json')
ST = os.path.join(B, '连续性', '.进程断点.json')
OUTDIR = os.path.join(B, '断点')


def main():
    reason = ' '.join(__import__('sys').argv[1:]) or '引擎重启'
    now = time.time()
    iso = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sig = {'at': iso, 'ts': now, 'reason': reason, 'grace': 8}
    json.dump(sig, open(SIG, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    try:
        d = json.load(open(ST, encoding='utf-8'))
    except Exception:
        d = {}
    running = {k: v for k, v in d.items() if v.get('state') == 'running'}
    os.makedirs(OUTDIR, exist_ok=True)
    fn = os.path.join(OUTDIR, '断点-%s.md' % datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    L = ['# 断点文件（%s）' % iso, '',
         '> 广播原因：%s。引擎重启后由 壳下挂 把这里的内容接回对话。' % reason, '',
         '| 任务 | 状态 | 停在哪 | 开始时间 |', '|---|---|---|---|']
    for k, v in running.items():
        L.append('| %s | %s | %s | %s |' % (
            k, v.get('state'), (v.get('step') or v.get('goal') or '')[:60],
            datetime.datetime.fromtimestamp(v.get('started', now)).strftime('%H:%M:%S')))
    if not running:
        L.append('| （无） | — | 没有任何任务正在跑 | — |')
    L += ['', '## 给接手的我', '',
          '- 这些任务**接着做**，别从头来；做完 `python3 记忆档案/断点.py done <任务名>`。',
          '- 队列里同时会有「续跑：<任务名>」条目，两边对得上就说明接上了。']
    open(fn, 'w', encoding='utf-8').write('\n'.join(L) + '\n')

    # 2026-11-28（引路人：「生成后注入虚拟引擎中的相关区」）：
    # 同步写进虚拟引擎的接续包区（engine-standby/handover-*），新窗口起来就是这份先读。
    try:
        hs = os.path.expanduser('~/.dsh/engine-standby')
        os.makedirs(hs, exist_ok=True)
        hp = os.path.join(hs, 'handover-%s-断点.md' % datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
        open(hp, 'w', encoding='utf-8').write('# 接续包（含断点）· %s\n\n%s\n' % (iso, '\n'.join(L)))
        print('已注入虚拟引擎接续区：%s' % hp)
    except Exception as e:
        print('接续区注入失败：%s' % e)
    print('已广播：%s；快照 %d 条 → %s' % (reason, len(running), fn))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
