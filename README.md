# Codex Context Reminder

[简体中文](README.zh-CN.md) | English

A local-only CLI that watches Codex session token usage and reminds you to create a handoff summary before context compression gets risky.

It reads local `token_count` events from `~/.codex/sessions/.../rollout-*.jsonl`, prints the latest context usage, and optionally shows a macOS notification when the current conversation crosses warning thresholds.

## Why

Long Codex threads are useful while a task is still active, but they can become fragile near the context limit. This tool gives you an early, human-controlled reminder:

- `70%`: consider creating a handoff at the next phase boundary
- `85%`: finish the current small step and create a handoff soon

It does not compress anything automatically. You decide when to generate the summary and whether to open a new thread.

## Install

From a local checkout:

```bash
python3 -m pip install .
```

Or run without installing:

```bash
python3 -m codex_context_reminder
```

## Usage

Check once:

```bash
codex-context-reminder
```

Watch every 60 seconds:

```bash
codex-context-reminder --watch --interval 60
```

Watch and show macOS notifications:

```bash
codex-context-reminder --watch --interval 60 --notify
```

Print the copy-ready handoff prompt:

```bash
codex-context-reminder --prompt
```

Use a specific session file:

```bash
codex-context-reminder --file ~/.codex/sessions/2026/05/27/rollout-example.jsonl
```

Test notification behavior without waiting for a large context:

```bash
codex-context-reminder --warn 1 --urgent 2 --notify
```

## Output

Example:

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

When the status is `WARN` or `URGENT`, the CLI also prints a copy-ready prompt asking Codex to generate a compact handoff summary with goals, completed work, key files, confirmed facts, open questions, risks, and next steps.

Machine-readable JSON:

```bash
codex-context-reminder --json
```

## Privacy

This tool is intentionally boring:

- local files only
- no network calls
- no model calls
- no Codex configuration changes
- no automatic compression or thread creation

It only reads Codex session JSONL files and optionally asks macOS to display a local notification.

## Development

Run tests:

```bash
python3 -m unittest discover -s tests
```

Compile-check:

```bash
PYTHONPYCACHEPREFIX=/tmp/codex-context-reminder-pycache python3 -m py_compile codex_context_reminder/*.py token_context_reminder.py
```

The root `token_context_reminder.py` file is a convenience wrapper for local use. The packaged CLI command is `codex-context-reminder`.
