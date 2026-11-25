#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""虚拟对话 · 只读镜像（维护者 2026-11-25：会话被吞/引擎挂掉时的备用副本）

真实对话由引擎写在 ~/.dsh/sessions/<workspace>/session-<id>/session.v4.jsonl.zstd。
本脚本只读它，增量解压成明文镜像：

  $DSH_HOME/engine-standby/dialog-mirror/<sid>.jsonl   全事件明文（只读副本）
  $DSH_HOME/engine-standby/dialog-mirror/index.json    会话索引（标题/事件数/最后时间/大小/hash）
  $DSH_HOME/engine-standby/dialog-mirror/<sid>.md      可读对话（--export 生成）
  $DSH_HOME/engine-standby/handover-<时间>.md          接续包（--handover 生成）

用途：主引擎挂了（g 了）→ 镜像还在 → 新窗口用接续包接上，对话不丢。

铁律：
  - 对真实会话只 open(..., 'rb') 读，绝不写、不移动、不删。
  - 镜像目录只增；源被重写（事件数变少）时才备份旧镜像再覆盖，并记 events。

用法：
  python3 虚拟对话.py --once            # 单次同步（默认）
  python3 虚拟对话.py --watch           # 常驻，60 秒一轮（--interval N 可调）
  python3 虚拟对话.py --list            # 看镜像状态
  python3 虚拟对话.py --export SID      # 导出可读对话 md
  python3 虚拟对话.py --handover [N]    # 出接续包：最近 N 条消息（默认 8）
  python3 虚拟对话.py --verify          # 抽查镜像与源的行数一致性
"""
import os, sys, json, time, glob, hashlib, subprocess

HOME = os.path.expanduser('~')
DSH_HOME = os.environ.get('DSH_HOME') or os.path.join(HOME, '.dsh')
SESS_ROOT = os.path.join(DSH_HOME, 'sessions')
MIRROR = os.path.join(DSH_HOME, 'engine-standby', 'dialog-mirror')
INDEX = os.path.join(MIRROR, 'index.json')
INTERVAL = int(os.environ.get('VIRTUAL_DIALOG_INTERVAL', '60'))
# 轮换参数（2026-11-25 维护者定）：镜像按「源是否还在 + 天数」清，handover 只留最近 N 份
ROTATE_DAYS = int(os.environ.get('DIALOG_MIRROR_KEEP_DAYS', '7'))
KEEP_HANDOVER = int(os.environ.get('DIALOG_KEEP_HANDOVER', '10'))
KEEP_RECENT = 5          # 最近 5 个会话的镜像永不因天数删除
KEEP_SYNC_LOG_LINES = 2000


def log(msg):
    line = '%s %s' % (time.strftime('%m-%d %T'), msg)
    print(line, flush=True)
    try:
        with open(os.path.join(MIRROR, 'sync.log'), 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def sh(cmd, timeout=120):
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def read_events(path):
    """zstd 解压 → 事件行列表（只读源文件）。返回 (行列表, 错误)"""
    code, out, err = sh(['zstd', '-dc', path])
    if code != 0:
        return None, (err.decode('utf-8', 'replace')[:200] or 'zstd 解压失败')
    lines = [l for l in out.decode('utf-8', 'replace').split('\n') if l.strip()]
    return lines, None


def _size_ms(path, size):
    """轻量指纹：大小 + mtime（避免每轮整读大文件）"""
    try:
        return '%d_%d' % (size, int(os.path.getmtime(path)))
    except OSError:
        return str(size)


def sha8(data):
    return hashlib.sha1(data).hexdigest()[:8]


def load_index():
    try:
        with open(INDEX, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_index(idx):
    os.makedirs(MIRROR, exist_ok=True)
    tmp = INDEX + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(idx, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, INDEX)


def summarize(lines):
    """抽标题与最后时间，供索引与接续包用"""
    title, last_t = '', 0
    for l in lines:
        if '"session/title"' in l:
            try:
                o = json.loads(l)
                t = (o.get('data') or {}).get('title')
                if t:
                    title = t
                last_t = max(last_t, o.get('time') or 0)
            except Exception:
                pass
        elif '"time"' in l:
            try:
                last_t = max(last_t, json.loads(l).get('time') or 0)
            except Exception:
                pass
    return title, last_t


def sync_one(path, idx):
    """同步一个会话。返回 'new' / 'append' / 'rewrite' / 'same' / 'error:...'"""
    sid = os.path.basename(os.path.dirname(path))
    ws = os.path.basename(os.path.dirname(os.path.dirname(path)))
    try:
        src_bytes = os.path.getsize(path)
    except OSError as e:
        return 'error:%s' % e

    rec = idx.get(sid) or {}
    lines, err = read_events(path)
    if err:
        return 'error:' + err
    n = len(lines)
    prev = int(rec.get('events') or 0)
    dst = os.path.join(MIRROR, sid + '.jsonl')

    os.makedirs(MIRROR, exist_ok=True)
    state = 'same'
    if prev == 0 or not os.path.exists(dst):
        with open(dst, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
        state = 'new'
    elif n > prev:
        with open(dst, 'a', encoding='utf-8') as f:
            f.write('\n'.join(lines[prev:]) + '\n')
        state = 'append'
    elif n < prev:
        # 源被重写/压缩（引擎压缩历史）→ 旧镜像留档，再覆盖（记 events，不静默）
        bak = dst + '.bak-' + time.strftime('%Y%m%d-%H%M%S')
        try:
            os.replace(dst, bak)
        except Exception:
            pass
        with open(dst, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
        state = 'rewrite'
        _append_event(sid, 'rewrite %d→%d 事件，旧镜像 %s' % (prev, n, os.path.basename(bak)))

    title, last_t = summarize(lines)
    idx[sid] = {
        'title': title or rec.get('title') or '',
        'workspace': ws,
        'events': n,
        'last_time': last_t,
        'last_seen': time.strftime('%Y-%m-%d %H:%M:%S'),
        'src_bytes': src_bytes,
        'src_hash': _size_ms(path, src_bytes),
        'mirror': dst,
    }
    return state


def _append_event(sid, note):
    try:
        os.makedirs(MIRROR, exist_ok=True)
        with open(os.path.join(MIRROR, 'events.jsonl'), 'a', encoding='utf-8') as f:
            f.write(json.dumps({'at': time.strftime('%Y-%m-%d %H:%M:%S'), 'sid': sid,
                                'note': note}, ensure_ascii=False) + '\n')
    except Exception:
        pass


def all_session_files():
    return sorted(glob.glob(os.path.join(SESS_ROOT, '*', 'session-*', 'session.v4.jsonl.zstd')))


def sync_all(only_changed=True):
    idx = load_index()
    counts = {}
    for p in all_session_files():
        sid = os.path.basename(os.path.dirname(p))
        if only_changed:
            try:
                if abs(os.path.getmtime(p) - float((idx.get(sid) or {}).get('src_mtime') or 0)) < 0.5:
                    continue
            except OSError:
                continue
        st = sync_one(p, idx)
        counts[st] = counts.get(st, 0) + 1
        try:
            idx[sid]['src_mtime'] = os.path.getmtime(p)
        except Exception:
            pass
    save_index(idx)
    return counts, len(idx)


def dialog_lines(sid, limit=None):
    """从镜像抽对话（用户/助手文本），跳过 reasoning 与系统注入"""
    dst = os.path.join(MIRROR, sid + '.jsonl')
    out = []
    try:
        fh = open(dst, encoding='utf-8')
    except OSError:
        return out
    with fh:
        for l in fh:
            l = l.strip()
            if not l:
                continue
            try:
                o = json.loads(l)
            except Exception:
                continue
            t = o.get('type')
            d = o.get('data') or {}
            if t not in ('user/message', 'assistant/message'):
                continue
            msg = d.get('message') or {}
            parts = []
            for c in (msg.get('content') or []) if isinstance(msg, dict) else []:
                if isinstance(c, dict) and c.get('type') == 'text' and c.get('text'):
                    parts.append(c['text'])
            txt = '\n'.join(parts).strip()
            if not txt:
                continue
            if t == 'user/message' and txt.startswith(('<system-reminder>', 'Current runtime context',
                                                       '<project_instructions>', 'Time sampled',
                                                       '[SCHEDULE REMINDER]')):
                continue
            who = '用户' if t == 'user/message' else '助手'
            ts = o.get('time') or 0
            when = time.strftime('%m-%d %H:%M:%S', time.localtime(ts / 1000)) if ts else '?'
            out.append((when, who, txt))
    if limit:
        out = out[-limit:]
    return out


def rotate(days=None, keep_handover=None, apply=False):
    """轮换：只删「源还在、且超过 N 天没活动」的镜像；
    源已消失（正是吞对话的救援副本）一律保留，标 orphan。
    handover 保留最近 N 份（内容可由镜像重生成，删了不丢东西）。"""
    days = ROTATE_DAYS if days is None else days
    keep_handover = KEEP_HANDOVER if keep_handover is None else keep_handover
    idx = load_index()
    now = time.time()
    src_ids = {os.path.basename(os.path.dirname(p)) for p in all_session_files()}
    rows = sorted(idx.items(), key=lambda kv: kv[1].get('last_time') or 0, reverse=True)
    drop, orphan, freed = [], [], 0
    for i, (sid, m) in enumerate(rows):
        dst = os.path.join(MIRROR, sid + '.jsonl')
        if not os.path.exists(dst):
            continue
        if sid not in src_ids:
            m['orphan'] = True
            orphan.append(sid)
            continue
        if i < KEEP_RECENT:
            continue
        last = (m.get('last_time') or 0) / 1000
        if last and now - last > days * 86400:
            freed += os.path.getsize(dst)
            drop.append(dst)
            if apply:
                try:
                    os.remove(dst)
                    m['rotated'] = time.strftime('%Y-%m-%d')
                except OSError:
                    pass
    # handover：留最近 N 份
    hs = sorted(glob.glob(os.path.join(DSH_HOME, 'engine-standby', 'handover-*.md')),
                key=os.path.getmtime, reverse=True)
    hdrop = hs[keep_handover:]
    if apply:
        for h in hdrop:
            try:
                os.remove(h)
            except OSError:
                pass
    # sync.log 截断
    if apply:
        logp = os.path.join(MIRROR, 'sync.log')
        try:
            with open(logp, encoding='utf-8') as f:
                lines = f.readlines()
            if len(lines) > KEEP_SYNC_LOG_LINES:
                with open(logp, 'w', encoding='utf-8') as f:
                    f.writelines(lines[-KEEP_SYNC_LOG_LINES:])
        except OSError:
            pass
        save_index(idx)
    out = {'模式': '执行' if apply else '预演（加 --apply 才真删）',
           '镜像超过 %d 天可删' % days: [os.path.basename(x) for x in drop],
           '可回收 MB': round(freed / 1048576, 1),
           'handover 多余份数': len(hdrop),
           '源已消失·保留(orphan)': orphan,
           '保留最近': KEEP_RECENT}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def do_export(sid):
    rows = dialog_lines(sid)
    if not rows:
        print('没有可导出的对话：', sid)
        return 1
    dst = os.path.join(MIRROR, sid + '.md')
    with open(dst, 'w', encoding='utf-8') as f:
        f.write('# 对话导出 · %s\n\n> 只读镜像导出，共 %d 条消息\n\n' % (sid, len(rows)))
        for when, who, txt in rows:
            f.write('## %s · %s\n\n%s\n\n' % (when, who, txt[:4000]))
    print('已导出', dst, '（%d 条）' % len(rows))
    return 0


def do_handover(n=8):
    idx = load_index()
    recent = sorted(idx.items(), key=lambda kv: kv[1].get('last_time') or 0, reverse=True)[:2]
    if not recent:
        print('镜像里没有会话，先跑 --once')
        return 1
    ts = time.strftime('%Y%m%d-%H%M%S')
    dst = os.path.join(DSH_HOME, 'engine-standby', 'handover-%s.md' % ts)
    with open(dst, 'w', encoding='utf-8') as f:
        f.write('# 接续包 %s\n\n' % time.strftime('%Y-%m-%d %H:%M:%S'))
        f.write('> 主引擎不可用时，新窗口读这份就能接上。来源=只读镜像，不含系统注入。\n\n')
        for sid, meta in recent:
            f.write('## 会话 %s（%s）\n\n' % (sid, meta.get('title') or '无标题'))
            last = meta.get('last_time') or 0
            f.write('- 事件 %s · 最后活动 %s\n' % (meta.get('events'), time.strftime('%m-%d %H:%M:%S', time.localtime(last / 1000)) if last else '?'))
            f.write('- 镜像：`%s`\n\n' % meta.get('mirror'))
            for when, who, txt in dialog_lines(sid, limit=n):
                f.write('**%s · %s**\n\n%s\n\n' % (when, who, txt[:1200]))
    print('已生成接续包', dst)
    return 0


def do_list():
    idx = load_index()
    if not idx:
        print('镜像为空（先 --once）')
        return 0
    rows = sorted(idx.items(), key=lambda kv: kv[1].get('last_time') or 0, reverse=True)
    for sid, m in rows[:15]:
        last = m.get('last_time') or 0
        when = time.strftime('%m-%d %H:%M', time.localtime(last / 1000)) if last else '?'
        size = 0
        try:
            size = os.path.getsize(m.get('mirror') or '')
        except OSError:
            pass
        print('%-42s %-18s %5s 事件 %7d KB  %s' % (sid, (m.get('title') or '')[:18], m.get('events'), size // 1024, when))
    print('共 %d 个会话（镜像 %s）' % (len(idx), MIRROR))
    return 0


def do_verify():
    idx = load_index()
    bad, lag = 0, []
    for sid, m in idx.items():
        src = None
        for p in all_session_files():
            if os.path.basename(os.path.dirname(p)) == sid:
                src = p
                break
        if not src:
            continue
        lines, err = read_events(src)
        if err:
            print('✗', sid, err)
            bad += 1
            continue
        mirror = os.path.join(MIRROR, sid + '.jsonl')
        try:
            with open(mirror, encoding='utf-8') as f:
                got = sum(1 for l in f if l.strip())
        except OSError:
            print('✗', sid, '镜像缺失')
            bad += 1
            continue
        if got > len(lines):
            print('✗', sid, '镜像多于源（源被改写但未同步）源 %d / 镜像 %d' % (len(lines), got))
            bad += 1
        elif got < len(lines):
            lag.append((sid, len(lines) - got))
    for sid, d in lag[:5]:
        print('…', sid, '镜像落后 %d 事件（正常，下一轮同步）' % d)
    print('校验完成：%d 个会话，%d 个不一致，%d 个滞后' % (len(idx), bad, len(lag)))
    return 0 if bad == 0 else 2


def main():
    args = sys.argv[1:]
    global INTERVAL
    if '--interval' in args:
        try:
            INTERVAL = int(args[args.index('--interval') + 1])
        except Exception:
            pass
    if '--rotate' in args:
        _apply = '--apply' in args
        _days = None
        if '--days' in args:
            try:
                _days = int(args[args.index('--days') + 1])
            except Exception:
                _days = None
        return rotate(days=_days, apply=_apply)
    if '--export' in args:
        i = args.index('--export')
        sid = args[i + 1] if len(args) > i + 1 else ''
        return do_export(sid)
    if '--handover' in args:
        n = 8
        i = args.index('--handover')
        if len(args) > i + 1 and args[i + 1].isdigit():
            n = int(args[i + 1])
        return do_handover(n)
    if '--list' in args:
        return do_list()
    if '--verify' in args:
        return do_verify()
    if '--watch' in args:
        log('虚拟对话启动（只读镜像，%d 秒一轮；每小时轮换一次）' % INTERVAL)
        rounds = 0
        every = max(1, 3600 // max(INTERVAL, 30))  # 约一小时一次
        while True:
            try:
                c, total = sync_all()
                if any(k != 'same' for k in c):
                    log('同步 %s（共 %d 会话）' % (json.dumps(c, ensure_ascii=False), total))
            except Exception as e:
                log('轮次异常: ' + str(e)[:160])
            rounds += 1
            if rounds % every == 0:
                try:
                    import io as _io, contextlib as _cl
                    buf = _io.StringIO()
                    with _cl.redirect_stdout(buf):
                        rotate(apply=True)
                    log('轮换: ' + buf.getvalue().strip().replace('\n', ' ')[:160])
                except Exception as e:
                    log('轮换异常: ' + str(e)[:120])
            time.sleep(INTERVAL)
    # 默认 --once
    c, total = sync_all()
    rotate(apply=True)
    print(json.dumps({'同步': c, '会话数': total, '镜像': MIRROR}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
