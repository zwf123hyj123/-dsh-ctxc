# 修复：调度域 schema 体检

## 问题（真实现场）

`/tmp/dsh-web.log` 里的一行：

```
schedule (@deepseek-ai/dsh-schedule): DomainError: domain 'schedule':
stored record 'schedule-a293dfc8-…' in table 'tasks' does not match its schema
ZodError: deliveryHistory.earlierRecordsUnavailable → expected boolean, received undefined
```

一条手写进去的任务缺了 `deliveryHistory.earlierRecordsUnavailable`，导致**整个 schedule 域激活失败**
（`1 entry did not activate`）：所有定时任务一起不加载，工具表里连调度工具都消失。

症状看起来是「工具没了」，实际是「域没起来」。这类问题在 proot 长驻 Agent 上尤其隐蔽——
没人会天天翻 `dsh-web.log`，而任务的消失没有任何显式报错。

## 修复

`调度体检.py`：不依赖引擎，直接按 schema 校验 `~/.dsh/storages/schedule.json`。

- `record` 必须有 `id/kind/title/prompt/rrule/scheduledAt`，且 `id` 与键一致；
- `record` 里**不许**有 `lastDelivery`（那是外层字段）；
- `target.kind` 必须存在；
- `deliveryHistory.earlierRecordsUnavailable` 必须是布尔、`records` 必须是数组；
- 同一标题出现多条 → 报出来（重名任务最难查）。

接入：`工具体检.py` 每次开机多查一项「调度域 schema」，不合规会写进 `脑干层来件.md`。

## 用法

```sh
python3 调度体检.py           # 通过退出 0，不合规退出 1 并列出前 10 处
```

## 教训

外部往引擎私有存储写东西，**坏一条等于坏一域**。
要么按全字段校验后再写，要么根本不写——我选了后者。
