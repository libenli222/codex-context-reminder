---
name: codex-context-reminder
description: Local-only Codex context usage monitor and handoff workflow. Use when the user wants to check Codex token/context usage, watch for high context occupancy, receive reminders before context compression, generate or use a handoff prompt, install or run the codex-context-reminder CLI, or decide whether to compress/open a new Codex conversation.
---

# Codex Context Reminder

## Overview

Use this skill to help users monitor local Codex session context usage and decide when to create a handoff summary before context compression. Keep the workflow human-controlled: the tool reminds and prints a copy-ready prompt, but it never compresses context, creates new conversations, edits Codex configuration, calls a model, or sends data over the network.

## Quick Start

Prefer the packaged CLI when the repository is available:

```bash
python3 -m codex_context_reminder
python3 -m codex_context_reminder --watch --interval 60 --notify
python3 -m codex_context_reminder --prompt
```

When the packaged CLI is not installed or the skill has been installed standalone, run the bundled script:

```bash
python3 scripts/token_context_reminder.py
python3 scripts/token_context_reminder.py --watch --interval 60 --notify
python3 scripts/token_context_reminder.py --prompt
```

Interpret the status as:

- `OK`: context is still roomy; no handoff needed yet.
- `WARN`: recommend generating a handoff at the next phase boundary.
- `URGENT`: finish the current small step, then generate a handoff soon.

## Workflow

1. Inspect the user's intent: checking current usage, running a watcher, testing notifications, or preparing a handoff.
2. Run the CLI with the least intrusive command that satisfies the request.
3. Explain the result in human terms: current context percent, last-call input/cached/output tokens, and whether handoff is needed.
4. If status is `WARN` or `URGENT`, provide the printed handoff prompt and remind the user that they decide whether to compress or start a new conversation.
5. If notifications fail on macOS, run a low-threshold test such as `--warn 1 --urgent 2 --notify` and inspect the error; do not change system notification settings without the user's approval.

## Handoff Guidance

When the user decides to create a handoff, ask Codex to summarize:

- current goal
- project or working directory
- completed work
- key files and paths
- confirmed facts
- open questions
- risks and cautions
- recommended next step
- a ready-to-paste prompt for the next conversation

The default bundled prompt already asks for these fields and explicitly separates confirmed facts from pending or inferred items.

## Safety

- Treat `~/.codex/sessions/.../rollout-*.jsonl` as local private data.
- Do not upload session logs or paste large raw JSONL content unless the user explicitly asks.
- Do not present cached input as free or invisible usage; explain that caching can reduce repeated processing but usage meters may still move.
- Keep monitoring intervals conservative, usually 60 seconds or longer, unless the user is testing.
