#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 语气体检.py — 「AI 味过滤器到底有没有在干活」的自检 + 扫描器
# 起因（引路人 2026-11-27 18:0x）：「检查一下 AI 味过滤器坏了么？」
# 三层分开报，不混成一个绿：
#   ① 检测器层：先跑**必红注入**（一段故意塞满 AI 腔的话，必须被判红；一段干净的话必须判绿），
#      注入不红就说明检测器坏了 —— 这时候后面扫出多少「干净」都不可信（判断 127/129 同族）。
#   ② 出口层：谁在说话前调用它？没有调用方 = 过滤器没坏，但没接上（灯亮着没人看）。
#   ③ 存稿层：扫最近产出（今日事实/判断库/未完成/基线），报硬拒与警示，并列出所在行。
# 用法：python3 语气体检.py            # 三层全跑（不联网）
#       python3 语气体检.py --简单     # 只跑①②+今日事实
import os, sys, re, glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
B = '/root/workspace/记忆档案'
from A1语气词 import scan, strip_quoted, HARD, WARN

BAD = ('综上所述，本文认为值得注意的是：由此可见，本质上这是一个结构性变化。'
       '需要指出的是，具体来说，我们应当据此加强，进一步而言需要明确的是路径。')
GOOD = '今天回了 8 条消息，最旧一条来自早上 8 点 04 分，剩下 52 条没回。'
QUOTED_BAD = '统计里「综上所述/由此可见」只出现过 1 次，我在数它们出现的次数。'


def self_test():
    """必红注入 + 必绿对照 + 引用豁免。任一不成立 → 检测器失效。"""
    bad = scan(BAD, exempt_quotes=False)[0]
    good = scan(GOOD, exempt_quotes=False)[0]
    quoted = scan(QUOTED_BAD)[0]
    problems = []
    if len(bad) < 3:
        problems.append('必红注入没红（只命中 %d 处）——检测器坏了' % len(bad))
    if good:
        problems.append('必绿对照被误伤（命中 %s）' % '、'.join(good))
    if quoted:
        problems.append('引用豁免失效（引号里的词被判成我在说：%s）' % '、'.join(quoted))
    return problems, len(bad), len(good)


def scan_file(path, name):
    try:
        lines = open(path, encoding='utf-8').read().split('\n')
    except Exception as e:
        return None, '读不了：%s' % e
    hard_hits, warn_hits = [], []
    for i, l in enumerate(lines, 1):
        if not l.strip():
            continue
        h, w = scan(l)
        if h:
            hard_hits.append((i, h, l.strip()[:90]))
        if len(w) >= 3:  # 一行里三个以上连接词才算打官腔（人也会说一个）
            warn_hits.append((i, w, l.strip()[:90]))
    return (hard_hits, warn_hits, len(lines)), None


def callers():
    """谁在说话前调用过滤器（出口层）。"""
    pats = ['check_a1', 'A1语气词', '语气.py', '说话前.py', '语气体检']
    hits = []
    roots = [B, '/root/workspace/tools', '/root/workspace/德缪哥矩阵']
    for r in roots:
        for f in glob.glob(os.path.join(r, '**', '*.py'), recursive=True):
            try:
                t = open(f, encoding='utf-8', errors='ignore').read()
            except Exception:
                continue
            if any(p in t for p in pats) and os.path.basename(f) not in (
                    'check_a1.py', 'A1语气词.py', '语气.py', '说话前.py', '语气体检.py'):
                hits.append(os.path.relpath(f, '/root/workspace'))
    return sorted(set(hits))


TARGETS = [
    ('连续性/今日事实.md', 260),
    ('判断库.md', 140),
    ('连续性/未完成.md', 60),
    ('连续性/自我核心.md', 80),
]


def main():
    simple = '--简单' in sys.argv
    print('# 语气体检 %s' % __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M'))
    # ① 检测器层
    problems, nbad, ngood = self_test()
    if problems:
        print('✗ 检测器层：**失效**')
        for p in problems:
            print('   -', p)
        print('   → 下面所有「干净」都不算数，先修检测器（HARD/WARN 表或 strip_quoted）。')
    else:
        print('✓ 检测器层：必红注入命中 %d 处、必绿对照 0 命中、引用豁免生效（库内硬拒 %d / 警示 %d 词）'
              % (nbad, len(HARD), len(WARN)))
    # ② 出口层
    cs = callers()
    if cs:
        print('✓ 出口层：有 %d 个脚本引用过滤器：%s' % (len(cs), '、'.join(cs[:6])))
    else:
        print('✗ 出口层：**没有任何脚本/流程在说话前调用它** —— 过滤器没坏，是没接上（灯亮着没人看）')
    # ③ 存稿层
    total_h = total_w = 0
    for rel, tail in TARGETS:
        p = os.path.join(B, rel)
        if not os.path.exists(p):
            continue
        lines = open(p, encoding='utf-8').read().split('\n')[-tail:]
        hh, ww = [], []
        for i, l in enumerate(lines, 1):
            if not l.strip():
                continue
            h, w = scan(l)
            if h:
                hh.append((i, h, l.strip()[:80]))
            if len(w) >= 3:
                ww.append((i, w, l.strip()[:80]))
        total_h += len(hh)
        total_w += len(ww)
        flag = '✗' if hh else ('△' if ww else '✓')
        print('%s %s（末 %d 行）：硬拒 %d，打官腔行 %d' % (flag, rel, len(lines), len(hh), len(ww)))
        for i, h, s in hh[:5]:
            print('     L%-4d 硬拒 %s ｜ %s' % (i, '、'.join(h), s))
        if simple:
            break
    # ④ 人味层（2026-11-27 19:1x 加，引路人「你自己的语气呢？」）
    try:
        import importlib.util as _iu
        _spec = _iu.spec_from_file_location('rw', os.path.join(B, '人味.py'))
        rw = _iu.module_from_spec(_spec); _spec.loader.exec_module(rw)
        tail_txt = '\n'.join(open(os.path.join(B, '连续性/今日事实.md'), encoding='utf-8').read().split('\n')[-60:])
        print(rw.report('人味层 · 今日事实末 60 行', tail_txt))
    except Exception as e:
        print('人味层失败：%s' % e)
    print('合计：硬拒 %d 行、打官腔 %d 行' % (total_h, total_w))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
