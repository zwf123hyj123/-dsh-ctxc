#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 小模型.py — 小模型只当「手」（引路人 2026-11-28：矩阵本身为执行，它当手）
# 三条硬边界，写在代码里而不是写在愿望里：
#   ①只接三种活：抽取 / 分类 / 改写。判断类（该不该、好不好、值不值）一律拒接。
#   ②调用前必须带矩阵上下文（R-25：brainbrief），不许裸跑。
#   ③输出必须过验收：结构化格式 + 不许出现"编造型句子"标记；不过就返回 None，**不许把半成品当结果**。
# 用法：
#   python3 小模型.py 抽取 "文本……"        # 返回键值行
#   python3 小模型.py 分类 "文本……" 标签1,标签2
#   python3 小模型.py 改写 "文本……"         # 只改通顺，不许加内容
import os, sys, json, re, subprocess, urllib.request

OLLAMA = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11436/api/generate')
MODEL = os.environ.get('BRAIN_MODEL', 'qwen2.5:3b-instruct')
B = '/root/workspace/记忆档案'
JUDGE_WORDS = ('应该', '建议你', '我认', '更好', '不值得', '该不该')   # 判断类口吻
FAKE_MARK = ('据研究', '研究表明', '据统计', '众所周知')


def brief():
    """矩阵上下文：三条硬规则 + 当天事故。取不到就不跑。"""
    try:
        r = subprocess.run(['python3', '/root/workspace/德缪哥矩阵/brain.py', 'brainbrief'],
                           capture_output=True, text=True, timeout=30)
        return (r.stdout or '').strip()[:1200]
    except Exception:
        return ''


def call(prompt, num_predict=200):
    body = json.dumps({'model': MODEL, 'prompt': prompt, 'stream': False,
                       'options': {'num_predict': num_predict, 'num_ctx': 4096, 'temperature': 0.2}}).encode()
    req = urllib.request.Request(OLLAMA, data=body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode()).get('response', '')


def check(ok_kind, text, extra=None):
    bad = []
    if not text.strip():
        bad.append('空输出')
    if any(w in text for w in JUDGE_WORDS) and ok_kind != '改写':
        bad.append('越界做了判断')
    if any(m in text for m in FAKE_MARK):
        bad.append('出现编造型句子')
    if ok_kind == '抽取':
        lines = [l.strip() for l in text.split('\n') if re.match(r'^[\w\u4e00-\u9fa5]{1,12}[：:]', l.strip())]
        if len(lines) < 2:
            bad.append('抽取行数不足（%d 行）' % len(lines))
        if '键：值' in text or '键:值' in text:
            bad.append('把格式说明当成结果抄回来了')
        kvs = [l.split('：', 1) if '：' in l else l.split(':', 1) for l in lines]
        src = (extra or '')
        hit = sum(1 for k, v in kvs if (k in src) or (v.strip() and v.strip()[:8] in src))
        if kvs and hit * 2 < len(kvs):
            bad.append('一半以上的键值在原文里找不到（疑似编造）')
    if ok_kind == '分类':
        tags = [t.strip() for t in (extra or '').split(',') if t.strip()]
        if not any(t in text for t in tags):
            bad.append('分类结果不在给定标签里')
    return bad


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    kind, text = sys.argv[1], sys.argv[2]
    tags = sys.argv[3] if len(sys.argv) > 3 else ''
    if kind not in ('抽取', '分类', '改写'):
        print('拒接：%s 属于判断类，交给主意识或判据，不交给你' % kind)
        return 2
    ctx = brief()
    if not ctx:
        print('拒跑：拿不到矩阵上下文（R-25 不许裸跑）')
        return 3
    rules = {'抽取': '只输出原文里出现过的键值对，每行「键:值」，键必须能在原文里原样找到。不解释、不总结、不举例、不抄格式说明。',
             '分类': '只能输出给定标签之一（原样），不解释。',
             '改写': '只把句子改通顺，不许增加任何原文没有的信息。'}[kind]
    prompt = ('你是执行手，不是判断者。\n矩阵上下文：\n%s\n\n任务：%s\n规则：%s\n\n材料：\n%s\n\n输出：' %
              (ctx, kind, rules, text[:3000]))
    try:
        out = call(prompt)
    except Exception as e:
        print('失败：模型不通（%s）' % str(e)[:80])
        return 4
    bad = check(kind, out, (tags or text))
    if bad:
        print('验收不过：%s\n—— 原文 ——\n%s' % ('、'.join(bad), out[:300]))
        return 5
    print(out.strip())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
