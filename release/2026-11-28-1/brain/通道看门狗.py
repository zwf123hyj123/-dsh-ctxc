#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 通道看门狗 — 引路人 2026-11-28 定的三条时效规则：
#   ① 单次调用超时 5 分钟  → 判「没 token 了」，看门狗提醒
#   ② 单次调用超时 10 分钟 → 判「没任务了」（这一轮等于没跑），重派
#   ③ 3 分钟内超时 ≥10 次 → 同样判「没 token」，**换一个有的通道**
# 它只探通道健康（不干活），每 120 秒一轮；状态写 记忆档案/通道状态.json，出事走 通知.py（懂作息）。
import os, sys, json, time, datetime, subprocess, urllib.request, urllib.error

B = '/root/workspace/记忆档案'
STATE = os.path.join(B, '通道状态.json')
LOG = os.path.join(B, '通道日志.jsonl')
NOTIFY = os.path.join(B, '通知.py')
LOCAL = 'http://127.0.0.1:11436/api/version'
CLOUD = 'http://127.0.0.1:18326/v1/models'
PROBE_TIMEOUT = 300          # 单次调用最多等 5 分钟＝判没 token 的线
HARD_TIMEOUT = 600           # 10 分钟＝这轮算没跑
WINDOW, FAILS = 180, 10      # 3 分钟内 10 次超时


def probe(url, timeout):
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'dsh-watchdog'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read(64)
        return True, time.time() - t0, ''
    except Exception as e:
        return False, time.time() - t0, str(e)[:80]


def load():
    try:
        return json.load(open(STATE, encoding='utf-8'))
    except Exception:
        return {'fails': [], 'channel': 'cloud', 'switched_at': ''}


def save(d):
    json.dump(d, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def notify(title, text):
    subprocess.run(['python3', NOTIFY, title, text], capture_output=True, text=True)


def main(once=False):
    d = load()
    while True:
        ok_c, sec_c, err_c = probe(CLOUD, PROBE_TIMEOUT)
        ok_l, sec_l, err_l = probe(LOCAL, 10)
        now = time.time()
        fails = [f for f in d.get('fails', []) if now - f < WINDOW]
        if not ok_c:
            if sec_c >= HARD_TIMEOUT:
                grade = '没任务了（这轮等于没跑）'
            elif sec_c >= 60:      # urllib 到点就抛，这里用实测耗时近似
                grade = '没 token 了'
            else:
                grade = '失败'
            fails.append(now)
            with open(LOG, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'at': datetime.datetime.now().strftime('%m-%d %H:%M:%S'),
                                    'cloud_ok': ok_c, 'sec': round(sec_c, 1), 'grade': grade,
                                    'err': err_c, 'local_ok': ok_l}, ensure_ascii=False) + '\n')
            if len(fails) >= FAILS:
                # 3 分钟 10 次 → 换通道
                target = 'local' if ok_l else 'none'
                if d.get('channel') != target:
                    d['channel'] = target
                    d['switched_at'] = datetime.datetime.now().strftime('%m-%d %H:%M')
                    notify('通道换了', '云端连续 %d 次超时（%s），已切到 %s' %
                           (len(fails), grade, '本地 ollama' if ok_l else '无可用通道'))
                    fails = []
        else:
            fails = []
            if d.get('channel') == 'local' and ok_c:
                d['channel'] = 'cloud'
                d['switched_at'] = datetime.datetime.now().strftime('%m-%d %H:%M')
        d['fails'] = fails
        d['last'] = datetime.datetime.now().strftime('%m-%d %H:%M:%S')
        d['cloud_ok'], d['local_ok'] = ok_c, ok_l
        d['cloud_sec'], d['local_sec'] = round(sec_c, 2), round(sec_l, 2)
        save(d)
        if once:
            print(json.dumps({'cloud': [ok_c, round(sec_c, 1)], 'local': [ok_l, round(sec_l, 1)],
                              'channel': d['channel'], 'fails': len(fails)}, ensure_ascii=False))
            return 0
        # 2026-11-28 修：原来 120 秒一轮，3 分钟内最多 2 次探测，永远凑不到「10 次」——
        # 判据永远不成立，等于没装。改成 15 秒一轮（正常时只花 0.2 秒），3 分钟能探 12 次。
        time.sleep(15)


if __name__ == '__main__':
    raise SystemExit(main('--once' in sys.argv))
