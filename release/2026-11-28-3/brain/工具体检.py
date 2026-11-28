#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 工具体检.py — 拿 工具表.md 里的「能验的」逐项核对，缺的写进来件
# 引路人 2026-11-28：「写个工具表，重启后自动加载」
import os, sys, json, subprocess, datetime

B = '/root/workspace/记忆档案'
INBOX = os.path.join(B, '脑干层来件.md')

CHECKS = [
    ('壳 /usr/local/bin/dsh', lambda: os.path.exists('/usr/local/bin/dsh')),
    ('壳·看护循环', lambda: 'while :; do' in open('/usr/local/bin/dsh', encoding='utf-8', errors='ignore').read()),
    ('壳·reload 标识', lambda: 'reload.json' in open('/usr/local/bin/dsh', encoding='utf-8', errors='ignore').read()),
    ('壳·断点清扫', lambda: '断点.py sweep' in open('/usr/local/bin/dsh', encoding='utf-8', errors='ignore').read()),
    ('断点脚本', lambda: os.path.exists(os.path.join(B, '断点.py'))),
    ('断点广播', lambda: os.path.exists(os.path.join(B, '断点广播.py'))),
    ('壳下挂', lambda: os.path.exists(os.path.join(B, '壳下挂.py'))),
    ('通道看门狗', lambda: os.path.exists(os.path.join(B, '通道看门狗.py'))),
    ('通知出口（懂作息）', lambda: os.path.exists(os.path.join(B, '通知.py'))),
    ('采集体检', lambda: os.path.exists(os.path.join(B, '采集体检.py'))),
    ('手机桥 patch', lambda: os.path.exists('/opt/dsh-app/phone/phone.patch.yml')),
    ('dsh-xingxi 插件', lambda: os.path.exists(os.path.expanduser('~/.dsh/xingxi/config.json'))),
    ('profile 里 dsh-llm 软链', lambda: os.path.exists(os.path.expanduser('~/.dsh/profiles/web/node_modules/@deepseek-ai/dsh-llm'))),
]


def proc_running(name):
    out = subprocess.run(['ps', '-eo', 'cmd'], capture_output=True, text=True).stdout
    return any(name in l and 'grep' not in l for l in out.split('\n'))


def main():
    missing = []
    for name, fn in CHECKS:
        try:
            ok = bool(fn())
        except Exception:
            ok = False
        if not ok:
            missing.append(name)
    for p in ('壳下挂.py', '通道看门狗.py'):
        if not proc_running(p):
            missing.append('进程：%s 没在跑' % p)
    print('# 工具体检 %s' % datetime.datetime.now().strftime('%F %H:%M'))
    print('✓ 全部在位' if not missing else '✗ 缺 %d 项：%s' % (len(missing), '、'.join(missing)))
    if missing:
        txt = open(INBOX, encoding='utf-8').read() if os.path.exists(INBOX) else '# 脑干层来件\n\n## 要我定的\n\n## 异常且脑干修不了\n\n'
        for m in missing:
            if m in txt:
                continue
            txt = txt.replace('## 异常且脑干修不了\n\n', '## 异常且脑干修不了\n\n- %s 工具体检缺：%s\n'
                              % (datetime.date.today().isoformat(), m), 1)
        open(INBOX, 'w', encoding='utf-8').write(txt)
    return 1 if missing else 0


if __name__ == '__main__':
    raise SystemExit(main())
