#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ctxc.py v2 — 混合并发压缩：小段本地（Ollama），大段上云（OpenAI 兼容端点），并发跑、按序合并。
# 用法:
#   cat 长文.txt | python3 ctxc.py                     # ≤本地容量: 全本地；超出: 本地+云端并发
#   python3 ctxc.py 文件.md --mode short --keep-paths
# 环境变量:
#   CTXC_API            本地端点（默认 http://127.0.0.1:11436/v1/chat/completions）
#   CTXC_MODEL          本地模型（默认 qwen2.5:1.5b-instruct）
#   CTXC_LOCAL_MAX      本地最多压多少字（默认 2600，超出部分上云）
#   CTXC_CLOUD_API      云端 OpenAI 兼容端点（不配则超出部分原样保留+指针）
#   CTXC_CLOUD_KEY      云端 API Key
#   CTXC_CLOUD_MODEL    云端模型名（默认 deepseek-chat）
import sys, json, os, re, argparse, time
from concurrent.futures import ThreadPoolExecutor
import urllib.request

LOCAL_API = os.environ.get("CTXC_API", "http://127.0.0.1:11436/v1/chat/completions")
LOCAL_MODEL = os.environ.get("CTXC_MODEL", "qwen2.5:1.5b-instruct")
LOCAL_MAX = int(os.environ.get("CTXC_LOCAL_MAX", "2600"))
CLOUD_API = os.environ.get("CTXC_CLOUD_API", "")
CLOUD_KEY = os.environ.get("CTXC_CLOUD_KEY", "")
CLOUD_MODEL = os.environ.get("CTXC_CLOUD_MODEL", "")
OFM_SETTINGS = os.path.expanduser("~/.dsh/our-free-model/settings.json")

def resolve_cloud():
    """云端端点解析：显式 env 优先；否则走 dsh-our-free-model 的本地网关（自动切换）。"""
    if CLOUD_API:
        return CLOUD_API, CLOUD_KEY, CLOUD_MODEL or "kilo-auto/free"
    try:
        j = json.load(open(OFM_SETTINGS))
        relay = j.get("chanGateway", {}).get("relay", {})
        if relay.get("enabled"):
            api = "http://%s:%s/v1/chat/completions" % (
                relay.get("host", "127.0.0.1"), relay.get("port", 18326))
            return api, relay.get("key", ""), CLOUD_MODEL or "kilo-auto/free"
    except Exception:
        pass
    return "", "", ""
CHUNK = 380
SYSTEM = "你是上下文压缩器。把输入压缩成中文要点，每点不超过20字；保留数字、名称、结论，去掉客套与重复。只输出要点，不要解释。"

def chunk_text(text):
    paras = re.split(r"(?<=[。！？\n])", text)
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) > CHUNK and cur:
            chunks.append(cur)
            cur = p
        else:
            cur += p
    if cur:
        chunks.append(cur)
    return chunks

def call(api, key, model, chunk, timeout=90):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": chunk},
        ],
        "max_tokens": 90,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(api, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read().decode("utf-8"))
    return (j["choices"][0]["message"].get("content") or "").strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", help="文件（缺省读 stdin）")
    ap.add_argument("--mode", choices=["bullets", "short"], default="bullets")
    ap.add_argument("--keep-paths", action="store_true")
    ap.add_argument("--no-hybrid", action="store_true", help="禁用云端，超出部分原样保留")
    args = ap.parse_args()

    if args.file:
        src = "file:" + args.file
        text = open(args.file, encoding="utf-8").read()
    else:
        src = "stdin"
        text = sys.stdin.read()

    chunks = chunk_text(text)
    # 分配：前段给本地（累计 ≤ LOCAL_MAX），后段上云
    local_chunks, cloud_chunks, acc = [], [], 0
    for c in chunks:
        if acc + len(c) <= LOCAL_MAX:
            local_chunks.append(c)
            acc += len(c)
        else:
            cloud_chunks.append(c)

    cloud_api, cloud_key, cloud_model = resolve_cloud()
    use_cloud = bool(cloud_chunks) and bool(cloud_api) and not args.no_hybrid

    def run_local(cs):
        out = []
        for c in cs:
            try:
                out.append(call(LOCAL_API, "", LOCAL_MODEL, c))
                print("[ctxc] 本地块完成 (%d 字)" % len(c), file=sys.stderr)
            except Exception as e:
                out.append("[本地压缩失败: %s] 原文见: %s" % (e, src))
        return out

    def _cloud_models():
        """候选模型：默认自动路由 + 网关模型列表（自动切换镜像）。"""
        cands = [cloud_model] if cloud_model else []
        try:
            req = urllib.request.Request(
                cloud_api.rsplit("/chat/completions", 1)[0] + "/models",
                headers={"Authorization": "Bearer " + cloud_key} if cloud_key else {})
            with urllib.request.urlopen(req, timeout=20) as r:
                j = json.loads(r.read().decode("utf-8"))
            for m in j.get("data", []):
                mid = m.get("id")
                if mid and mid not in cands:
                    cands.append(mid)
        except Exception:
            pass
        return cands[:4]

    def run_cloud(cs):
        out = []
        models = _cloud_models()
        for c in cs:
            done = False
            for m in models:
                try:
                    out.append(call(cloud_api, cloud_key, m, c))
                    print("[ctxc] 云端块完成 (%d 字, %s)" % (len(c), m), file=sys.stderr)
                    done = True
                    break
                except Exception:
                    continue
            if not done:
                out.append("[云端压缩失败（已试自动切换）] 原文见: %s" % src)
        return out

    t0 = time.time()
    if use_cloud:
        # 并发：本地串行组 与 云端串行组 同时跑
        with ThreadPoolExecutor(max_workers=2) as ex:
            f_local = ex.submit(run_local, local_chunks)
            f_cloud = ex.submit(run_cloud, cloud_chunks)
            local_out = f_local.result()
            cloud_out = f_cloud.result()
    else:
        local_out = run_local(local_chunks)
        cloud_out = []
        if cloud_chunks:
            note = "（%d 块共 %d 字超出本地容量：云端端点未配置，原样保留）" % (
                len(cloud_chunks), sum(len(c) for c in cloud_chunks))
            cloud_out.append(note)
            for c in cloud_chunks:
                cloud_out.append("  · " + c.strip().replace("\n", " ")[:120] + ("…" if len(c) > 120 else ""))

    if args.keep_paths:
        print("# 来源: %s" % src)
    print("\n".join(local_out + cloud_out))
    print("[ctxc] 完成：本地 %d 块 / 云端 %d 块，耗时 %.1fs" % (
        len(local_chunks), len(cloud_chunks) if use_cloud else 0, time.time() - t0), file=sys.stderr)

if __name__ == "__main__":
    main()
