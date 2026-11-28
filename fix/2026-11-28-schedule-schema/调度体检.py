#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 调度体检.py — 防止「外部写坏一条，整域不加载」
# 背景（2026-11-28 判断 178）：我手写了一条任务，缺 deliveryHistory.earlierRecordsUnavailable，
#   dsh-schedule 域激活失败（1 entry did not activate），所有定时任务一起不加载，
#   工具表里连调度工具都消失——报错只留在 /tmp/dsh-web.log 里。
# 用法：python3 调度体检.py [--fix]
import json, os, sys, shutil, datetime

P = os.path.expanduser('~/.dsh/storages/schedule.json')


def validate(path=P):
    bad = []
    try:
        d = json.load(open(path, encoding='utf-8'))
    except Exception as e:
        return [('整个文件', 'JSON 解析失败: %s' % e)]
    tasks = (d.get('tables') or {}).get('tasks')
    if not isinstance(tasks, dict):
        return [('tables.tasks', '缺失或不是对象')]
    seen = {}
    for sid, rec in tasks.items():
        r = rec.get('record') or {}
        for f in ('id', 'kind', 'title', 'prompt', 'rrule', 'scheduledAt'):
            if f not in r:
                bad.append((sid, 'record 缺 %s' % f))
        if r.get('id') and r['id'] != sid:
            bad.append((sid, 'record.id 与键不一致'))
        if 'lastDelivery' in r:
            bad.append((sid, 'record 里不该有 lastDelivery（应在 record 外）'))
        tgt = rec.get('target') or {}
        if 'kind' not in tgt:
            bad.append((sid, 'target.kind 缺失'))
        dh = rec.get('deliveryHistory')
        if not isinstance(dh, dict):
            bad.append((sid, 'deliveryHistory 不是对象'))
        else:
            if not isinstance(dh.get('earlierRecordsUnavailable'), bool):
                bad.append((sid, 'deliveryHistory.earlierRecordsUnavailable 必须是布尔'))
            if not isinstance(dh.get('records'), list):
                bad.append((sid, 'deliveryHistory.records 必须是数组'))
        if r.get('prompt') and not isinstance(r['prompt'], str):
            bad.append((sid, 'prompt 不是字符串'))
        shot = r.get('title') or ''
        seen.setdefault(shot, []).append(sid)
    for title, ids in seen.items():
        if title and len(ids) > 1:
            bad.append((ids[0], '标题重复 %s（共 %d 条）' % (title, len(ids))))
    return bad


def main():
    bad = validate()
    if not bad:
        print('调度体检：通过（%d 条任务）' % len((json.load(open(P, encoding='utf-8'))['tables']['tasks'])))
        return 0
    print('调度体检：✗ %d 处不合规' % len(bad))
    for sid, why in bad[:10]:
        print('  - %s：%s' % (sid[:30], why))
    print('提示：坏记录会让整个 schedule 域不加载；先备份再修。')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
