#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 三维体检.py — 「全门类 / 全行业」同时看 知识 + 方法 + 情报 + 使用
# 引路人 2026-11-27 17:15：「全门类各行业那个更为全部知识、方法、情报」→ 17:3x：「各行业=全行业」
#
# 口径（写死，不许事后改口径凑数）：
#   知识轴：知识计数.py 唯一口径（`##` 小节、正文≥200字节，按文件名关键词归门类/行业，一文可属多类）。
#   方法轴：判断库.md 条目 + 德缪哥矩阵/方法层.md 条目，正文关键词命中即算 1 条。
#   情报轴：情报流水文件小节数（官方源日志/每日情报/官网补齐/缺口清单/EigenFlux/情报目录），
#           命中**门类词 或 情报视角词**（INTEL_KW）——官方源说的是「制裁/军演」，不说「兵法」，
#           不补这层映射，兵法与谋略会永远是 0（判断 131：口径没覆盖 ≠ 确实没采）。
#   使用轴：知识/判据调用.jsonl 命中该门类/行业的次数（判据 128：不用的东西看起来比实际强）。
#
# 「全行业」的定义：GB/T 4754-2017 的 20 个门类（A–T，法定全覆盖）+ 24 个重点细分行业（重点观察，不声称全覆盖）。
# 输出：知识/三维基线-<日期>.md 与 .三维基线.json
import os, re, json, glob, importlib.util, datetime, collections

ARCH = '/root/workspace/记忆档案'
KNOW = os.path.join(ARCH, '知识')
RAW = os.path.join(KNOW, '原始')
OUT = os.path.join(KNOW, '三维基线-%s.md' % datetime.date.today().isoformat())
JSON = os.path.join(KNOW, '.三维基线.json')
FLOOR = 3


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


gk = _load(os.path.join(ARCH, '知识门类体检.py'), 'gk')
gi = _load(os.path.join(ARCH, '知识行业体检.py'), 'gi')
kc = _load(os.path.join(ARCH, '知识计数.py'), 'kc')
GATES, FINE = gk.GATES, gi.INDUSTRY

# ---------- 全行业：ISIC Rev.4（联合国国际标准产业分类，A–U 共 21 个门类） ----------
# 引路人 2026-11-27 17:5x：「不要急、慌，这是要扩大至全球的」——
# 所以行业骨架改用全球可比口径 ISIC Rev.4（方括号是该门类对应的 GB/T 4754 字母，国内落地对照）。
# 关键词中英并列：现在语料是中文，英文词基本不命中，等外语采集上线才会有数（这条写在报告的口径里，不假装有）。
IND_ISIC = {
    'A 农业林业渔业［GB A］': ['农业', '林业', '渔业', '畜牧', '种植', '养殖', '粮食', '农产品',
                        'agriculture', 'fishery', 'forestry'],
    'B 采矿和采石［GB B］': ['采矿', '矿业', '矿产', '煤炭', '石油开采', '金属矿', '稀土', '锂矿', '采石',
                       'mining', 'quarrying'],
    'C 制造业［GB C］': ['制造', '工业', '机械', '化工', '汽车', '钢铁', '装备', '加工', '纺织', '食品加工',
                     'manufacturing', 'factory'],
    'D 电煤气蒸汽空调供应［GB D］': ['电力', '电网', '燃气', '供热', '发电', '储能', '光伏', '风电', '核电',
                            'electricity', 'power grid'],
    'E 供水污水处理废物管理［GB D/N］': ['供水', '污水', '废物', '垃圾', '回收', '水处理',
                                'water supply', 'waste'],
    'F 建筑业［GB E］': ['建筑', '施工', '基建', '桥梁', '装修', '建材', 'construction'],
    'G 批发零售与汽修［GB F］': ['零售', '批发', '电商', '渠道', '贸易', '超市', '带货',
                          'retail', 'wholesale'],
    'H 运输和储存［GB G］': ['交通', '物流', '航运', '铁路', '港口', '快递', '供应链', '运输', '仓储', '民航', '集运',
                       'transport', 'logistics', 'shipping'],
    'I 住宿和餐饮服务［GB H］': ['住宿', '餐饮', '酒店', '民宿', '饭店', 'hotel', 'restaurant'],
    'J 信息和通信［GB I］': ['信息', '软件', '互联网', '云计算', '通信', '平台', '算法', '数据', 'Agent', 'agent',
                       '芯片设计', '移动端', 'software', 'telecom'],
    'K 金融和保险［GB J］': ['金融', '银行', '证券', '保险', '投资', '量化', '支付', '基金', '信托',
                       'finance', 'insurance'],
    'L 房地产［GB K］': ['房地产', '楼市', '物业', '地产', '住房', 'real estate'],
    'M 专业科学技术活动［GB L/M］': ['咨询', '会计', '审计', '设计', '研发', '实验室', '专利', '论文', '广告',
                              'consulting', 'R&D'],
    'N 行政和辅助活动［GB L］': ['租赁', '人力', '招聘', '外包', '保安', '清洁', '行政', 'administrative'],
    'O 公共行政与国防［GB S］': ['政府', '政策', '监管', '治理', '法律', '制度', '社会保障', '国防', '军事', '公安',
                          'public administration', 'defence'],
    'P 教育［GB P］': ['教育', '培训', '学校', '教学', '课程', '考试', 'education', 'school'],
    'Q 人体健康和社会工作［GB Q］': ['卫生', '医疗', '医学', '护理', '疾病', '养老', '社会救助', '医院', '药物',
                             'health', 'hospital'],
    'R 艺术娱乐和文娱［GB R］': ['文化', '体育', '娱乐', '游戏', '影视', '文学', '艺术', '综艺', '出版',
                          'arts', 'entertainment'],
    'S 其他服务活动［GB O］': ['居民服务', '家政', '维修', '美容', '洗浴', '生活服务', '会员组织',
                        'other services'],
    'T 家庭作为雇主［GB O］': ['家庭雇佣', 'household employer'],
    'U 国际组织和机构［GB T］': ['联合国', '世卫', '世行', '世界银行', 'WTO', 'IMF', '国际组织', '全球治理',
                          'United Nations', 'international organization'],
}

# ---------- 情报视角词：只用于情报轴（judged mapping，不是同义词词典） ----------
# 依据：这个门类的人看这类情报就是他的素材（例：读兵法的人看的是制裁/军演/封锁/战争险）。
INTEL_KW = {
    '兵法与谋略': ['制裁', '军演', '封锁', '战争险', '出口管制', '实体清单', '军事', '备战', '演习',
              '威慑', '禁运'],
    '经济与金融': ['运价', '指数', 'SCFI', 'BDI', '国债', '利差', '汇率', '库存', '港口拥堵', 'GDP'],
    '地缘与政治': ['台海', '南海', '俄乌', '中东', '制裁', '峰会', '选举', '阵营'],
    '军事与国防': ['军演', '装备', '航展', '战区', '备战', '制裁', '出口管制', '实体清单'],
    '农业与生态': ['粮食', '农产品', '气候', '耕地', '干旱', '播种'],
    '法律与制度': ['法规', '条例', '政策', '监管', '判例', '立法'],
    '媒体与传播': ['舆论', '报道', '媒体', '社交平台', '辟谣'],
    '心理学': ['行为', '情绪', '动机'],
    '文学与艺术': ['文化', '影视', '综艺', '出版', '艺术'],
    '天文与宇宙': ['卫星', '航天', '太空', '发射'],
}
# 行业侧的情报视角词（同一条判断，逐行业给）
INTEL_KW_I = {
    '医疗卫生': ['医学', '医疗', '卫生', '疾病', '临床', '药物', '医院'],
    '国际组织与全球治理': ['联合国', '世行', '世界银行', '世卫', 'WTO', 'IMF'],
    '农业科技与食品': ['食品', '粮食', '农业', '农产品'],
    '文化体育娱乐': ['文化', '影视', '综艺', '体育', '出版'],
    '住宿餐饮与旅游': ['旅游', '酒店', '航空', '航线'],
    '建筑与基建': ['基建', '施工', '建材', '桥梁'],
    '居民与生活服务': ['家政', '维修', '生活服务'],
}


# 情报轴专用停用词：这些词在任何情报里都出现，命中它们不能证明「这块有情报」
GENERIC = ('信息', '数据', '平台', '治理', '政策', '法律', '制度', '监管', '投资', '渠道',
           '贸易', '加工', '工业', '装备', '研发', '技术服务')


def hits(text, table, extra=None, stop=None):
    out = []
    for group, kws in table.items():
        pool = list(kws) + (extra or {}).get(group, [])
        for kw in pool:
            if stop and kw in stop:
                continue
            if kw in text:
                out.append(group)
                break
    return out


# ---------- 知识轴 ----------
def axis_knowledge(tables):
    res = [collections.Counter() for _ in tables]
    for d in (RAW, KNOW):
        for f in glob.glob(os.path.join(d, '*.md')):
            name = os.path.basename(f)
            if any(m in name for m in gk.META):
                continue
            n = kc.count_items(f)
            if not n:
                continue
            for cnt, tb in zip(res, tables):
                for g in hits(name, tb):
                    cnt[g] += n
    return res


# ---------- 方法轴 ----------
JUDGE = re.compile(r'(?m)^(\d+)\.\s+\*\*(.+?)\*\*')


def method_blocks():
    blocks = []
    p = os.path.join(ARCH, '判断库.md')
    if os.path.exists(p):
        txt = open(p, encoding='utf-8').read()
        marks = list(JUDGE.finditer(txt))
        for k, m in enumerate(marks):
            end = marks[k + 1].start() if k + 1 < len(marks) else len(txt)
            blocks.append(m.group(0) + '\n' + txt[m.end():end])
    p2 = '/root/workspace/德缪哥矩阵/方法层.md'
    if os.path.exists(p2):
        t2 = open(p2, encoding='utf-8').read()
        blocks += re.split(r'(?m)^##\s+', t2)[1:]
    return blocks


def axis_method(tables, blocks):
    res = [collections.Counter() for _ in tables]
    for b in blocks:
        for cnt, tb in zip(res, tables):
            for g in hits(b, tb):
                cnt[g] += 1
    return res


# ---------- 情报轴 ----------
def intel_files():
    # 2026-11-27 17:40 修：原来还有 '2026-11-24-*.md' 这种宽匹配，把《战术知识-镜片库》《关系网络-多视角》
    # 这些**方法笔记**算成了情报，导致「医学与卫生」凭空多出 8 条情报（判断 129 同族：样本面错）。
    pats = ['官方源日志-*.md', '每日情报-*.md', '2026-11-24-官网补齐*.md', '2026-11-24-情报缺口清单.md',
            'EigenFlux-*.md', '情报总览-*.md', '关键情报-*.md']
    fs = []
    for p in pats:
        fs += glob.glob(os.path.join(KNOW, p))
    fs += [f for f in glob.glob('/root/workspace/情报/*.md') if os.path.basename(f) != 'README.md']
    return sorted(set(fs))


def axis_intel(tables, extras):
    res = [collections.Counter() for _ in tables]
    corpus, fs = [], intel_files()
    for f in fs:
        try:
            body = open(f, encoding='utf-8', errors='ignore').read()
        except Exception:
            body = ''
        corpus.append(body)
        # 2026-11-27 17:45 修：原来「整篇命中一次就算整篇小节数」——情报缺口清单里出现一个「健康」，
        # 医学门类就凭空多出 8 条情报（其实一个字都没写医学）。现在**按小节判**：哪一节真的提到，只算 1 条。
        secs = [x for x in re.split(r'(?m)^##\s+', body)[1:] if x.strip()]
        if not secs:
            secs = [body]
        head = os.path.basename(f)
        for cnt, tb, ex in zip(res, tables, extras):
            for sec in secs:
                text = head + '\n' + sec
                for g in hits(text, tb, ex, GENERIC):
                    cnt[g] += 1
    return res, len(fs), '\n'.join(corpus)


# ---------- 使用轴 ----------
def axis_usage(tables):
    res = [collections.Counter() for _ in tables]
    idx = {}
    p = os.path.join(KNOW, '判据索引.json')
    if os.path.exists(p):
        for it in json.load(open(p, encoding='utf-8')).get('items', []):
            idx[int(it['n'])] = (it.get('title') or '') + ' ' + (it.get('trigger') or '')
    total = 0
    p2 = os.path.join(KNOW, '判据调用.jsonl')
    if os.path.exists(p2):
        for line in open(p2, encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            n = int(r.get('n') or 0)
            scene = (r.get('scene') or '') + ' ' + idx.get(n, '')
            total += 1
            for cnt, tb in zip(res, tables):
                for g in hits(scene, tb):
                    cnt[g] += 1
    return res, total


# ---------- 语种：英文命中（判断 133 的判据：骨架全球 ≠ 语料全球，要有数才敢说） ----------
EN_WORD = re.compile(r'[A-Za-z][A-Za-z\-]{2,}')


# 英文片段：连续 40 个以上英文字符（可含空格/标点）。一个英文词夹在中文句子里不算「英文素材」——
# 否则 'Agent'、'health' 这种词会让 21 个行业里的 18 个显示「有英文」，那是假绿。
EN_RUN = re.compile(r"[A-Za-z][A-Za-z0-9 ,.'\"()\-]{39,}")


def axis_english(tables):
    """英文关键词命中的文件数：关键词必须**落在英文片段里**才算。"""
    res = [collections.Counter() for _ in tables]
    files = [f for f in glob.glob(os.path.join(KNOW, '*.md'))] + intel_files()
    for f in sorted(set(files)):
        try:
            t = open(f, encoding='utf-8', errors='ignore').read()
        except Exception:
            continue
        runs = ' \n'.join(EN_RUN.findall(t)).lower()
        if not runs:
            continue
        for cnt, tb in zip(res, tables):
            for g, kws in tb.items():
                if any(kw.isascii() and len(kw) > 2 and kw.lower() in runs for kw in kws):
                    cnt[g] += 1
    return res


def english_output():
    """我自己用英文写出来的东西有多少段（不是语料里有多少英文）。"""
    p = os.path.join(KNOW, '外语-读本.md')
    if not os.path.exists(p):
        return 0
    return len(re.findall(r'(?m)^##\s*第\s*\d+\s*段', open(p, encoding='utf-8').read()))


def status(k, m, i):
    # 情报门槛与知识同：<3 条就是「薄」，1 条不算有活水（否则一个词提一句就显示达标）
    if not m:
        return '缺方法'
    if i < FLOOR:
        return '缺情报'
    return '✓' if k >= FLOOR else '薄'


def render(L, title, names, K, M, I, U):
    rows = [(g, K[g], M[g], I[g], U[g]) for g in names]
    rows.sort(key=lambda r: (-(r[1] + r[2] + r[3]), r[0]))
    L += ['', '## %s（%d）' % (title, len(names)), '',
          '| 名称 | 知识 | 方法 | 情报 | 使用 | 状态 |', '|---|---|---|---|---|---|']
    for g, k, m, i, u in rows:
        L.append('| %s | %d | %d | %d | %d | %s |' % (g, k, m, i, u, status(k, m, i)))
    thin = [r[0] for r in rows if r[1] < FLOOR or not r[2] or r[3] < FLOOR]
    return rows, thin


def main():
    tables = [GATES, IND_ISIC, FINE]
    extras = [INTEL_KW, {}, INTEL_KW_I]
    KG = axis_knowledge(tables)
    blocks = method_blocks()
    MM = axis_method(tables, blocks)
    IG, nintel, corpus = axis_intel(tables, extras)
    UU, nuse = axis_usage(tables)
    EN = axis_english(tables)

    today = datetime.date.today().isoformat()
    L = ['# 三维基线 · 全门类 + 全行业（%s 实测）' % today, '',
         '> 四列口径：**知识**＝`知识/`+`原始/` 按 `##` 小节计（正文≥200字节，见 知识计数.py）；'
         '**方法**＝判断库+方法层里命中该门类的条目数；**情报**＝情报流水小节数（含情报视角词映射，见下）；'
         '**使用**＝判据调用记录命中次数（判据 128）。',
         '> 门槛：知识 ≥ %d（判据 116）；**方法为 0 或情报 < %d 一律记「缺」，无论知识多少**（判断 131：纸面厚不算数）。' % (FLOOR, FLOOR),
         '> 全行业定义：**ISIC Rev.4（联合国《所有经济活动的国际标准产业分类》）A–U 共 21 个门类**＝全球可比；'
         '方括号内是对应的 GB/T 4754 字母（国内落地对照）。后面的 24 个是**重点细分行业**（重点观察，不声称全覆盖）。',
         '> 情报视角词：官方源说的是「制裁/军演/出口管制」，不说「兵法」——把这层映射写死（`INTEL_KW`/`INTEL_KW_I`），'
         '否则读兵法的门类会永远判成 0 情报（判断 131）。']

    rows_g, thin_g = render(L, '一、全门类', list(GATES), KG[0], MM[0], IG[0], UU[0])
    rows_20, thin_20 = render(L, '二、全行业 · ISIC Rev.4（联合国标准，全球可比）', list(IND_ISIC), KG[1], MM[1], IG[1], UU[1])
    rows_24, thin_24 = render(L, '三、重点细分行业', list(FINE), KG[2], MM[2], IG[2], UU[2])

    def gap_list(names, K, M, I):
        g_m = [n for n in names if not M[n]]
        g_i = [n for n in names if not I[n]]
        return g_m, g_i

    m20, i20 = gap_list(list(IND_ISIC), KG[1], MM[1], IG[1])
    m24, i24 = gap_list(list(FINE), KG[2], MM[2], IG[2])
    L += ['', '## 四、缺口（按「缺什么」分，不按名字排）', '',
          '**ISIC 行业缺方法**：%s' % ('、'.join(m20) or '无'),
          '**ISIC 行业缺情报**：%s' % ('、'.join(i20) or '无'),
          '**细分行业（24）缺方法**：%s' % ('、'.join(m24) or '无'),
          '**细分行业（24）缺情报**：%s' % ('、'.join(i24) or '无'), '',
          '**总量**：方法条目 %d / 情报文件 %d / 调用记录 %d。' % (len(blocks), nintel, nuse), '',
          '## 五、语种（骨架全球 ≠ 语料全球）', '',
          '| 口径 | 有英文原文片段的门类/行业数 |', '|---|---|',
          '| 全门类 | %d |' % sum(v for v in EN[0].values()) if False else '| 全门类 | %d |' % len([k for k, v in EN[0].items() if v]),
          '| ISIC 全行业 | %d |' % len([k for k, v in EN[1].items() if v]),
          '| 重点细分 | %d |' % len([k for k, v in EN[2].items() if v]), '',
          '**我自己写出来的英文：%d 段**（`知识/外语-读本.md`）。' % english_output(), '',
          '> 读法：上面几个数是「有多少个门类/行业里有**英文原文片段**」（RSS/论文摘要/接口原文都算），不是篇数；'
          '最后一行才是**我能用英文产出多少**。两个数要分开看——输入有、输出没有，就是还没学会。'
          '现在中文语料占绝大多数，英文命中集中在少数几个门类——所以对外只说「骨架挂的是全球标准」，不说「已覆盖全球」。', '',
          '> 诚实边界：①方法与情报按关键词命中归一，回答「这块有没有东西」，不回答「有多深」——深度只能靠演练（M8）。'
          '②「重点细分行业」是我挑的 24 个，不是全行业；全行业只有 A–T 那 20 个门类算。'
          '③情报视角词是我写的映射判断，改它等于改口径，必须写理由。']
    open(OUT, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    json.dump({'门类': {g: {'知识': k, '方法': m, '情报': i, '使用': u} for g, k, m, i, u in rows_g},
               '全球行业ISIC': {g: {'知识': k, '方法': m, '情报': i, '使用': u} for g, k, m, i, u in rows_20},
               '细分行业': {g: {'知识': k, '方法': m, '情报': i, '使用': u} for g, k, m, i, u in rows_24},
               '缺口': {'门类': thin_g, '全球行业ISIC': thin_20, '细分行业': thin_24,
                      'ISIC缺方法': m20, 'ISIC缺情报': i20, '细分缺方法': m24, '细分缺情报': i24},
               '总量': {'方法条目': len(blocks), '情报文件': nintel, '调用记录': nuse},
               '语种': {'英文命中的门类数': len([k for k, v in EN[0].items() if v]),
                        '英文命中的ISIC行业数': len([k for k, v in EN[1].items() if v]),
                        '英文命中的细分行业数': len([k for k, v in EN[2].items() if v]),
                        '英文产出段数': english_output(),
                        '明细': {'门类': {k: v for k, v in EN[0].items() if v},
                                 'ISIC': {k: v for k, v in EN[1].items() if v},
                                 '细分': {k: v for k, v in EN[2].items() if v}}},
               'at': today},
              open(JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('# 三维基线 %s' % today)
    print('总量：方法 %d / 情报文件 %d / 调用 %d' % (len(blocks), nintel, nuse))
    print('\n门类(20)：三缺 %d' % len(thin_g))
    for g, k, m, i, u in rows_g[:8]:
        print('  %-12s %3d %3d %3d %3d' % (g, k, m, i, u))
    print('\nISIC 全行业(21)：三缺 %d' % len(thin_20))
    for g, k, m, i, u in rows_20[:10]:
        print('  %-16s %3d %3d %3d %3d' % (g, k, m, i, u))
    print('\n细分行业(24)：三缺 %d' % len(thin_24))
    print('ISIC 缺方法：', '、'.join(m20) or '无')
    print('ISIC 缺情报：', '、'.join(i20) or '无')
    print('细分缺方法：', '、'.join(m24) or '无')
    print('细分缺情报：', '、'.join(i24) or '无')
    print('\n语种：英文素材命中的门类 %d / ISIC 行业 %d / 细分 %d；我自己的英文产出 %d 段'
          % (len([k for k, v in EN[0].items() if v]), len([k for k, v in EN[1].items() if v]),
             len([k for k, v in EN[2].items() if v]), english_output()))
    print('\n→ %s' % OUT)


if __name__ == '__main__':
    main()
