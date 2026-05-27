# Codex Context Reminder

简体中文 | [English](README.md)

一个本地只读的命令行工具，用来监控 Codex 会话的上下文 token 使用情况，并在上下文压缩变得有风险之前提醒你生成交接摘要。

它会读取本地 `~/.codex/sessions/.../rollout-*.jsonl` 里的 `token_count` 事件，输出最近一次会话的上下文使用情况，并可在达到阈值时通过 macOS 通知提醒你。

## 为什么需要

长对话在任务仍然连续推进时很有用，但接近上下文上限后，自动压缩可能遗漏刚刚验证过的细节。这个工具给你一个提前量，让是否压缩、何时开新对话仍由人来判断：

- `70%`: 建议在下一个阶段边界生成 handoff
- `85%`: 建议完成当前小步骤后尽快生成 handoff

它不会自动压缩上下文，也不会自动创建新对话。它只提醒你，并附上可复制的交接摘要提示词。

## 安装

从本地仓库安装：

```bash
python3 -m pip install .
```

也可以不安装，直接运行：

```bash
python3 -m codex_context_reminder
```

## 使用

检查一次：

```bash
codex-context-reminder
```

每 60 秒监控一次：

```bash
codex-context-reminder --watch --interval 60
```

每 60 秒监控一次，并开启 macOS 通知：

```bash
codex-context-reminder --watch --interval 60 --notify
```

打印可复制的交接摘要提示词：

```bash
codex-context-reminder --prompt
```

指定某个 Codex session 文件：

```bash
codex-context-reminder --file ~/.codex/sessions/2026/05/27/rollout-example.jsonl
```

不等待真实上下文变大，直接测试提醒行为：

```bash
codex-context-reminder --warn 1 --urgent 2 --notify
```

## Codex Skill

这个仓库也包含一个 Codex Skill 包装层：

```text
skills/codex-context-reminder/
```

当你希望 Codex 帮你安装或运行提醒器、解释输出、判断是否需要 handoff、生成可复制的交接摘要提示词时，可以使用这个 Skill。它内置了一份 standalone 脚本：

```text
skills/codex-context-reminder/scripts/token_context_reminder.py
```

## 输出示例

```text
[OK] 上下文还比较宽裕，暂时不用压缩。
time: 2026-05-27T03:10:51.254Z
file: /Users/example/.codex/sessions/2026/05/27/rollout-example.jsonl
context: 69,999 / 258,400 tokens (27.1%)
last call: input=69,999, cached_input=69,504, uncached_input=495, output=218, reasoning_output=0, cache_hit=99.3%
thread total: input=1,362,213, cached_input=1,201,536, uncached_input=160,677, output=14,018, reasoning_output=4,487, total=1,376,231
usage windows: 5h=18.0%, 1w=47.0%
handoff prompt: run with --prompt when you want the copy-ready template.
```

当状态进入 `WARN` 或 `URGENT` 时，CLI 会额外输出一段可复制给 Codex 的 handoff 提示词，要求生成包含当前目标、已完成事项、关键文件、已确认事实、待确认问题、风险和下一步的紧凑交接摘要。

输出机器可读 JSON：

```bash
codex-context-reminder --json
```

## 隐私

这个工具刻意保持简单和克制：

- 只读取本地文件
- 不访问网络
- 不调用模型
- 不修改 Codex 配置
- 不自动压缩上下文
- 不自动创建新对话

它只读取 Codex session JSONL 文件，并在你启用 `--notify` 时调用 macOS 显示本地通知。

## 开发

运行测试：

```bash
python3 -m unittest discover -s tests
```

编译检查：

```bash
PYTHONPYCACHEPREFIX=/tmp/codex-context-reminder-pycache python3 -m py_compile codex_context_reminder/*.py token_context_reminder.py
```

根目录的 `token_context_reminder.py` 是本地便捷入口；正式安装后的命令是 `codex-context-reminder`。
