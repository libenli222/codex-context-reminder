"""Command line interface for codex-context-reminder."""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_SESSIONS_GLOB = "~/.codex/sessions/*/*/*/rollout-*.jsonl"

HANDOFF_PROMPT = """请帮我压缩当前上下文，生成一个可以直接带到新对话继续工作的交接摘要。

要求：
1. 控制在 800 字以内，优先保留可执行信息，不要写客套话。
2. 明确区分“已确认事实”和“待确认/推测”。
3. 不要遗漏关键路径、文件名、命令、数据口径、当前阻塞点和下一步。
4. 如果涉及代码改动，请列出已改文件、未完成验证、测试结果和风险点。
5. 如果涉及报告/数据分析，请列出口径、数据来源、已确认结论、待补数据和不能误写的注意事项。

请按这个结构输出：
- 当前目标：
- 项目/工作目录：
- 已完成事项：
- 关键文件/路径：
- 已确认结论：
- 待确认问题：
- 当前风险/注意事项：
- 下一步建议：
- 新对话启动提示词：
"""


@dataclass
class TokenSnapshot:
    path: Path
    timestamp: str
    context_window: int
    last_input: int
    last_cached_input: int
    last_output: int
    last_reasoning_output: int
    total_input: int
    total_cached_input: int
    total_output: int
    total_reasoning_output: int
    total_tokens: int
    primary_used_percent: float | None
    secondary_used_percent: float | None

    @property
    def context_percent(self) -> float:
        if self.context_window <= 0:
            return 0.0
        return self.last_input / self.context_window * 100

    @property
    def last_uncached_input(self) -> int:
        return max(self.last_input - self.last_cached_input, 0)

    @property
    def total_uncached_input(self) -> int:
        return max(self.total_input - self.total_cached_input, 0)

    @property
    def last_cache_percent(self) -> float:
        if self.last_input <= 0:
            return 0.0
        return self.last_cached_input / self.last_input * 100


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read local Codex token_count events and remind before context gets too full."
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Specific rollout JSONL file to inspect. Defaults to the latest Codex session.",
    )
    parser.add_argument(
        "--warn",
        type=float,
        default=70.0,
        help="Context percentage that prints a warning. Default: 70.",
    )
    parser.add_argument(
        "--urgent",
        type=float,
        default=85.0,
        help="Context percentage that prints an urgent warning. Default: 85.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Keep watching instead of checking once.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Watch interval in seconds. Default: 60.",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Show a macOS notification when warning or urgent thresholds are crossed.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the latest snapshot as JSON.",
    )
    parser.add_argument(
        "--prompt",
        action="store_true",
        help="Print the handoff prompt template and exit.",
    )
    return parser.parse_args(argv)


def latest_rollout() -> Path:
    candidates = [Path(p) for p in glob.glob(os.path.expanduser(DEFAULT_SESSIONS_GLOB))]
    if not candidates:
        raise FileNotFoundError("No Codex rollout JSONL files found under ~/.codex/sessions.")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def nested_get(data: dict[str, Any], path: tuple[str, ...], default: Any = 0) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def read_latest_snapshot(path: Path) -> TokenSnapshot:
    latest: dict[str, Any] | None = None
    with path.expanduser().open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "event_msg" and nested_get(event, ("payload", "type")) == "token_count":
                latest = event

    if latest is None:
        raise ValueError(f"No token_count event found in {path}.")

    info = nested_get(latest, ("payload", "info"), {})
    total = info.get("total_token_usage", {})
    last = info.get("last_token_usage", {})
    rate_limits = nested_get(latest, ("payload", "rate_limits"), {})

    return TokenSnapshot(
        path=path.expanduser(),
        timestamp=str(latest.get("timestamp", "")),
        context_window=int(info.get("model_context_window", 0) or 0),
        last_input=int(last.get("input_tokens", 0) or 0),
        last_cached_input=int(last.get("cached_input_tokens", 0) or 0),
        last_output=int(last.get("output_tokens", 0) or 0),
        last_reasoning_output=int(last.get("reasoning_output_tokens", 0) or 0),
        total_input=int(total.get("input_tokens", 0) or 0),
        total_cached_input=int(total.get("cached_input_tokens", 0) or 0),
        total_output=int(total.get("output_tokens", 0) or 0),
        total_reasoning_output=int(total.get("reasoning_output_tokens", 0) or 0),
        total_tokens=int(total.get("total_tokens", 0) or 0),
        primary_used_percent=nested_get(rate_limits, ("primary", "used_percent"), None),
        secondary_used_percent=nested_get(rate_limits, ("secondary", "used_percent"), None),
    )


def status_for(snapshot: TokenSnapshot, warn: float, urgent: float) -> tuple[str, str]:
    percent = snapshot.context_percent
    if percent >= urgent:
        return (
            "URGENT",
            "建议在当前小步骤完成后立刻生成 handoff，不要继续塞大量新材料。",
        )
    if percent >= warn:
        return (
            "WARN",
            "建议到阶段边界时生成 handoff；现在仍可继续完成手头小任务。",
        )
    return ("OK", "上下文还比较宽裕，暂时不用压缩。")


def format_snapshot(snapshot: TokenSnapshot, warn: float, urgent: float) -> str:
    status, advice = status_for(snapshot, warn, urgent)
    primary = "n/a" if snapshot.primary_used_percent is None else f"{snapshot.primary_used_percent:.1f}%"
    secondary = "n/a" if snapshot.secondary_used_percent is None else f"{snapshot.secondary_used_percent:.1f}%"
    lines = [
        f"[{status}] {advice}",
        f"time: {snapshot.timestamp}",
        f"file: {snapshot.path}",
        f"context: {snapshot.last_input:,} / {snapshot.context_window:,} tokens ({snapshot.context_percent:.1f}%)",
        f"last call: input={snapshot.last_input:,}, cached_input={snapshot.last_cached_input:,}, uncached_input={snapshot.last_uncached_input:,}, output={snapshot.last_output:,}, reasoning_output={snapshot.last_reasoning_output:,}, cache_hit={snapshot.last_cache_percent:.1f}%",
        f"thread total: input={snapshot.total_input:,}, cached_input={snapshot.total_cached_input:,}, uncached_input={snapshot.total_uncached_input:,}, output={snapshot.total_output:,}, reasoning_output={snapshot.total_reasoning_output:,}, total={snapshot.total_tokens:,}",
        f"usage windows: 5h={primary}, 1w={secondary}",
    ]
    if status in {"WARN", "URGENT"}:
        lines.extend(
            [
                "",
                "Copy this prompt when you decide to generate the handoff:",
                "```text",
                HANDOFF_PROMPT.strip(),
                "```",
            ]
        )
    else:
        lines.append("handoff prompt: run with --prompt when you want the copy-ready template.")
    return "\n".join(lines)


def snapshot_as_json(snapshot: TokenSnapshot, warn: float, urgent: float) -> str:
    status, advice = status_for(snapshot, warn, urgent)
    payload = {
        "status": status,
        "advice": advice,
        "timestamp": snapshot.timestamp,
        "file": str(snapshot.path),
        "context": {
            "input_tokens": snapshot.last_input,
            "window_tokens": snapshot.context_window,
            "used_percent": round(snapshot.context_percent, 2),
        },
        "last_call": {
            "input_tokens": snapshot.last_input,
            "cached_input_tokens": snapshot.last_cached_input,
            "uncached_input_tokens": snapshot.last_uncached_input,
            "output_tokens": snapshot.last_output,
            "reasoning_output_tokens": snapshot.last_reasoning_output,
            "cache_hit_percent": round(snapshot.last_cache_percent, 2),
        },
        "thread_total": {
            "input_tokens": snapshot.total_input,
            "cached_input_tokens": snapshot.total_cached_input,
            "uncached_input_tokens": snapshot.total_uncached_input,
            "output_tokens": snapshot.total_output,
            "reasoning_output_tokens": snapshot.total_reasoning_output,
            "total_tokens": snapshot.total_tokens,
        },
        "usage_windows": {
            "primary_used_percent": snapshot.primary_used_percent,
            "secondary_used_percent": snapshot.secondary_used_percent,
        },
        "handoff_prompt": HANDOFF_PROMPT.strip() if status in {"WARN", "URGENT"} else None,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def notify(title: str, body: str) -> None:
    script = """
on run argv
  display notification (item 2 of argv) with title (item 1 of argv)
end run
"""
    subprocess.run(["osascript", "-e", script, title, body], check=False)


def run_once(args: argparse.Namespace, last_notified_status: str | None = None) -> str | None:
    path = args.file.expanduser() if args.file else latest_rollout()
    snapshot = read_latest_snapshot(path)
    status, advice = status_for(snapshot, args.warn, args.urgent)

    if args.json:
        print(snapshot_as_json(snapshot, args.warn, args.urgent))
    else:
        print(format_snapshot(snapshot, args.warn, args.urgent))

    if args.notify and status in {"WARN", "URGENT"} and status != last_notified_status:
        notify(f"Codex context {status}", f"{snapshot.context_percent:.1f}% used. {advice}")
        return status
    return last_notified_status


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.prompt:
        print(HANDOFF_PROMPT.strip())
        return 0

    if args.warn >= args.urgent:
        print("--warn must be lower than --urgent.", file=sys.stderr)
        return 2

    try:
        if not args.watch:
            run_once(args)
            return 0

        last_notified_status: str | None = None
        while True:
            os.system("clear")
            last_notified_status = run_once(args, last_notified_status)
            print(f"\nWatching every {args.interval}s. Press Ctrl-C to stop.")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


__all__ = [
    "DEFAULT_SESSIONS_GLOB",
    "HANDOFF_PROMPT",
    "TokenSnapshot",
    "format_snapshot",
    "latest_rollout",
    "main",
    "read_latest_snapshot",
    "snapshot_as_json",
    "status_for",
]
