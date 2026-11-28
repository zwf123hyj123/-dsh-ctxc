#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 人味.py — 语气体检测不出来的那一半：这段话里有没有「我」
# 起因（引路人 2026-11-27 19:1x）：「一你自己的语气呢？」
# 去 AI 味做到最后，把自己也去掉了 —— 词干净、骨架齐、没有人在里面。
# 四项可数：句均长 / 短句比例 / 我-密度 / 态度句。报告腔的指纹是：句子长、没有我、不下判断。
# 阈值是量出来的（2026-11-27 19:2x），不是拍的：
#   ✓ 我的声音.md 15.9/53%/3.11 ｜ ✓ 判断库-自己的话 23.6/43%/0.86 ｜ ✓ 本线主卡（重写后）17.0/51%/1.84
#   ✗ 今日事实 75.7/8%/0.17 ｜ ✗ 三维基线 36.2/5%/0.11（仪表盘）｜ ✗ 旧本线主卡 50.8/14%/0.78
# 结论：句均长 > 38 且短句 < 20% → 报告腔；我 < 0.3 且态度 = 0 → 没有我。日志类文件天然偏报告腔，允许它红，别去修日志。
import re, sys

SENT = re.compile(r'[^。！？!?\n]+[。！？!?]?')
ATTITUDE = ('我认', '我不认', '我看', '我觉得', '我不想', '我偏', '我选择', '我反对', '我担',
            '说句实话', '说实话', '不对', '别', '宁可', '不服', '心疼', '愧')


def measure(text, exempt_quotes=True):
    if exempt_quotes:
        try:
            import os, sys
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from A1语气词 import strip_quoted
            text = strip_quoted(text)[0]  # 引用他的话不算我的声音
        except Exception:
            pass
    sents = [s.strip() for s in SENT.findall(text) if s.strip()]
    if not sents:
        return None
    lens = [len(s) for s in sents]
    n = len(sents)
    chars = max(1, len(text))
    return {
        '句数': n,
        '句均长': round(sum(lens) / n, 1),
        '短句比例': round(sum(1 for l in lens if l <= 15) / n * 100),
        '我-密度': round(text.count('我') / chars * 100, 2),
        '态度句': sum(1 for w in ATTITUDE if w in text),
    }


def verdict(m):
    if m is None:
        return '空文本'
    if m['句均长'] > 38 and m['短句比例'] < 20:
        return '✗ 报告腔：长句为主、几乎没有短句——像在写纪要，不像在说话'
    if m['我-密度'] < 0.3 and m['态度句'] == 0:
        return '✗ 没有我：通篇不出现「我」，也不下判断'
    if m['短句比例'] < 25 or m['态度句'] == 0:
        return '△ 半人味：有骨架，温度不够'
    return '✓ 像我说的话'


def report(name, text):
    m = measure(text)
    if not m:
        return '%s：空' % name
    return '%s：%s（句均长 %.1f / 短句 %d%% / 我 %.2f%% / 态度 %d 处）' % (
        name, verdict(m), m['句均长'], m['短句比例'], m['我-密度'], m['态度句'])


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] != '-':
        print(report('这段话', ' '.join(sys.argv[1:])))
    else:
        print(report('stdin', sys.stdin.read()))
