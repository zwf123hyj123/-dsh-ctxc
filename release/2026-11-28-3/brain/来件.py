#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 来件.py v2 — 只有「需要主意识」的才进 脑干层来件.md（引路人 2026-11-27：「只有需要主意识的你来」）
#
# 五类才归我（主意识）：
#   ① 方向/取舍：开线、停线、换口径、改规则——脑干没有权力替我定。
#   ② 脑干修不了：同一异常连续 3 次仍在（自动修复失败或根本没有修复器）。
#   ③ 不可逆/对外/花钱/隐私：删数据、发布、转账、外发、凭据。
#   ④ 判断冲突：两条规则打架，或两份数据互相矛盾，得我裁。
#   ⑤ 与我有关：他跟我说的话、要我回应的、触及人格与关系的。
#
# 不归我（留在日志，不进对话）：欠账数量在动（脑干自己在清）、单次抖动、能自动修的缺口、已完成流水。
import os, re, json, subprocess, datetime, hashlib

B = '/root/workspace/记忆档案'
INBOX = os.path.join(B, '脑干层来件.md')
STATE = os.path.join(B, '连续性', '.来件状态.json')

# 脑干自管：这些红灯是「进度」，不是「要你拍板」
SELF_RUN = ('收件箱：收件箱欠账', '知识层：待消化', '突触层', '跨层一致', '巡检有异常')
# 直接归我：出现一次就报
ASK_ME = ('发布', '转账', '支付', '凭据', '隐私', '删除', '矛盾', '规则冲突', '拍板')


def key_of(line):
    return hashlib.md5(re.sub(r'\d+', '#', line).encode('utf-8')).hexdigest()[:8]


def classify(line):
    if any(w in line for w in ASK_ME):
        return 'ask', '涉及不可逆/对外/隐私/裁断，必须我定'
    if any(w in line for w in SELF_RUN):
        return 'self', '脑干在自管（看进度即可，别打扰）'
    return 'watch', '不在自管清单，先记次数'


def main():
    r = subprocess.run(['python3', os.path.join(B, '自检.py')], capture_output=True, text=True, timeout=300)
    bad = [l.strip() for l in (r.stdout or '').split('\n') if l.strip().startswith('✗')]
    st = {}
    if os.path.exists(STATE):
        try:
            st = json.load(open(STATE, encoding='utf-8'))
        except Exception:
            st = {}
    today = datetime.date.today().isoformat()
    need, quiet = [], []
    for line in bad:
        k = key_of(line)
        rec = st.get(k, {'first': today, 'count': 0, 'line': line})
        if rec.get('last') != today:      # 一天只算一次，同一天反复跑不累计（不然三次调用就假升级）
            rec['count'] = rec.get('count', 0) + 1
        rec['last'] = today
        rec['line'] = line
        kind, why = classify(line)
        st[k] = rec
        if kind == 'ask':
            need.append((line, why))
        elif rec['count'] >= 3:
            # 自管项也会升级：连着 3 次没清掉，说明脑干卡住了，那是我的事
            need.append((line, '连续 %d 次仍在，脑干没清掉——升给主意识' % rec['count']))
        else:
            quiet.append((line, why, rec['count']))
    seen = {key_of(l) for l in bad}
    st = {k: v for k, v in st.items() if k in seen}  # 消失的条目不背次数，好了就归零
    json.dump(st, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    if not need:
        print('来件：无需主意识（%d 条留在日志自管）' % len(quiet))
        return 0
    txt = open(INBOX, encoding='utf-8').read() if os.path.exists(INBOX) else \
        '# 脑干层来件\n\n> 只有需要主意识的才进来。\n\n## 要我定的\n\n## 异常且脑干修不了\n\n## 已处理（留痕）\n'
    added = 0
    for line, why in need:
        k = key_of(line)
        if k in txt:
            continue
        txt = txt.replace('## 要我定的\n\n', '## 要我定的\n\n- %s `%s` %s\n  - 为什么归我：%s\n' % (today, k, line, why), 1)
        added += 1
    open(INBOX, 'w', encoding='utf-8').write(txt)
    print('来件：%d 条需要主意识（其余 %d 条脑干自管）' % (added, len(quiet)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
