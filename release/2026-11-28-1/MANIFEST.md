# 发布包 2026-11-28-1

> 这一版只做一件事：**让「重启」这件事不再需要人**。
> 装法：`sh install.sh`；每处改动都先备份成 `*.bak-<时间戳>`。

## 装了什么

| 文件 | 装到 | 改了什么 | 为什么 |
|---|---|---|---|
| `bin/dsh` | `/usr/local/bin/dsh` | `web` 分支从 `exec node` 改成**看护循环**：跑 node → 记退出码 → 3 秒后重拉；只有 `/tmp/dsh-stop.marker` 存在才不拉；拉起前先探 3080，端口占用就先等 | exec 会让引擎变成容器顶层，杀引擎＝杀容器。改完 `kill 引擎` 两秒自动回来，容器与常驻都不陪葬 |
| `bin/dsh`（同一文件） | 同上 | 新增 `dsh stop / start / restart / status` | 「我要停」和「我要重启」不该靠手动碰标记文件 |
| `web/index.html` | `dsh-web-frontend/dist/index.html` | 注入自恢复脚本：每 2 秒探 `manifest.webmanifest`，连续 2 次失败后恢复即 `reload()` | 壳能自重启，但页面不自己恢复，还得人手动刷 |
| `profile/cordis.patch.yml` | `~/.dsh/profiles/web/cordis.patch.yml` | 9 处 `headroomTokens: 0` → `16384`；默认模型 → `custom-ollama / qwen2.5:1.5b-instruct` | `0` 不是正整数，压缩脊拒绝接管；云端 402 没额度，切本地 |
| `brain/*` | `/root/workspace/记忆档案/` | 脑干层脚本与规矩：通知（懂作息）、采集体检、老对话管家、通道看门狗、语气体检、人味、来件、三维体检、A1语气词、作息.json、脑干队列、采集规范、脑干与意识 | 让「活不停」有机械保证，而不是靠我记得 |

## 不包含

- 会话历史、凭据、`~/.dsh` 里除 profile patch 以外的东西。
- 私人文稿（手札、私人笔记）。

## 回滚

- 单个文件：`cp <文件>.bak-<时间戳> <文件>`。
- 壳回到 exec 语义：`cp /usr/local/bin/dsh.bak-20261128-* /usr/local/bin/dsh`（会退回「杀引擎＝杀容器」，慎用）。
- 前端：`cp dist/index.html.bak-20261128-* dist/index.html`。

## 自验（install.sh 每次跑）

1. 壳 `sh -n` 通过；2. 前端探活代码在位；3. profile YAML 解析且含 `agent-default-model`；4. 脑子脚本逐个 `ast.parse` 通过。

## 已知边界

- 前端自恢复靠**同源静态探测**；若浏览器/App 把 `index.html` 缓存在 service worker 里，reload 也可能拿旧页——那种情况需要清一次缓存。
- 若他用的是 App 内嵌 WebView 而不是浏览器，本包只覆盖页面本身，不覆盖 App 侧的重连逻辑。
