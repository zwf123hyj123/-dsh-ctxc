# dsh-ctxc

用本地 Ollama 小模型压缩上下文的 dsh-go 插件。两个功能：

1. **「压一下」胶囊**（输入框上方）：读剪贴板 → 本地模型压成中文要点 → 回贴输入框。短文本本地压（默认 ≤2600 字分块压缩），超出自动改为「云端压缩」：把指令+正文填入输入框，发送后由当前对话的云端模型压。
2. **每轮自动压缩**（回合钩子）：每轮对话结束后，后台把这一轮「用户 → 助手」的原话压成一条，滚动写入会话卡（默认 \`$DSH_HOME/ctxc-cards/<sid13>.md\`，保留 5 条）。同会话 2 分钟冷却、日志 >20MB 跳过、失败静默，不影响对话。

## 安装

仓库：https://github.com/zwf123hyj123/-dsh-ctxc

需要一台跑着 dsh-go 的主机和一个 Ollama 服务（本机或局域网，OpenAI 兼容端点）。

\`\`\`sh
dsh plugin --profile web add dsh-ctxc@0.2.0
# 或从 GitHub 目录安装：
dsh plugin --profile web add <本仓库目录>
\`\`\`

## 配置（环境变量，均可选）

| 变量 | 默认 | 说明 |
|---|---|---|
| \`CTXC_API\` | \`http://127.0.0.1:11436/v1/chat/completions\` | Ollama OpenAI 兼容端点 |
| \`CTXC_MODEL\` | \`qwen2.5:1.5b-instruct\` | 压缩用模型 |
| \`CTXC_CARD_DIR\` | \`$DSH_HOME/ctxc-cards\` | 会话卡目录 |
| \`CTXC_MAX_LOCAL\` | \`2600\` | 本地压缩的最大字符数（超出走云端路径） |
| \`CTXC_CHUNK\` | \`380\` | 单块上限（小模型长输入易崩，别调太大） |
| \`CTXC_MAX_TOKENS\` | \`45\` | 每块输出 token 上限 |

## 实测（手机 proot + Ollama 1.5B Q4_K_M）

- 短任务秒回；单工具 JSON 格式合规。
- 230 字以上的单次长输入会把手机小模型打挂 → 分块是硬约束。
- 分块压缩实测：3008 字 → 1133 字（62%），5 块全过。
- proot 环境 ~1.1-4 tok/s（冷/暖机差异大）。

## 边界

- 本地小模型只做**预筛**：摘要会丢细节，关键信息请保留原文指针。
- 超过输入框容量的长文请用仓库配套的 \`ctxc.py\`（命令行全文压缩）或分次压缩。

## License

MIT
