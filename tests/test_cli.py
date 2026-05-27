import json
import unittest
from pathlib import Path

from codex_context_reminder.cli import (
    TokenSnapshot,
    read_latest_snapshot,
    snapshot_as_json,
    status_for,
)


def make_snapshot(last_input: int, context_window: int = 100) -> TokenSnapshot:
    return TokenSnapshot(
        path=Path("/tmp/rollout.jsonl"),
        timestamp="2026-05-27T00:00:00Z",
        context_window=context_window,
        last_input=last_input,
        last_cached_input=last_input // 2,
        last_output=10,
        last_reasoning_output=2,
        total_input=last_input * 2,
        total_cached_input=last_input,
        total_output=20,
        total_reasoning_output=4,
        total_tokens=last_input * 2 + 20,
        primary_used_percent=12.0,
        secondary_used_percent=34.0,
    )


class CliTests(unittest.TestCase):
    def test_status_thresholds(self):
        self.assertEqual(status_for(make_snapshot(69), 70, 85)[0], "OK")
        self.assertEqual(status_for(make_snapshot(70), 70, 85)[0], "WARN")
        self.assertEqual(status_for(make_snapshot(85), 70, 85)[0], "URGENT")

    def test_read_latest_snapshot_uses_last_token_count(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            rollout = Path(tmpdir) / "rollout.jsonl"
            rollout.write_text(
                "\n".join(
                    [
                        json.dumps({"type": "event_msg", "payload": {"type": "other"}}),
                        json.dumps(
                            {
                                "timestamp": "first",
                                "type": "event_msg",
                                "payload": {
                                    "type": "token_count",
                                    "info": {
                                        "model_context_window": 100,
                                        "total_token_usage": {
                                            "input_tokens": 10,
                                            "cached_input_tokens": 1,
                                            "output_tokens": 2,
                                            "reasoning_output_tokens": 3,
                                            "total_tokens": 12,
                                        },
                                        "last_token_usage": {
                                            "input_tokens": 10,
                                            "cached_input_tokens": 1,
                                            "output_tokens": 2,
                                            "reasoning_output_tokens": 3,
                                        },
                                    },
                                    "rate_limits": {},
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "timestamp": "second",
                                "type": "event_msg",
                                "payload": {
                                    "type": "token_count",
                                    "info": {
                                        "model_context_window": 200,
                                        "total_token_usage": {
                                            "input_tokens": 50,
                                            "cached_input_tokens": 20,
                                            "output_tokens": 5,
                                            "reasoning_output_tokens": 1,
                                            "total_tokens": 55,
                                        },
                                        "last_token_usage": {
                                            "input_tokens": 40,
                                            "cached_input_tokens": 10,
                                            "output_tokens": 4,
                                            "reasoning_output_tokens": 1,
                                        },
                                    },
                                    "rate_limits": {
                                        "primary": {"used_percent": 11.0},
                                        "secondary": {"used_percent": 22.0},
                                    },
                                },
                            }
                        ),
                    ]
                ),
                encoding="utf-8",
            )

            snapshot = read_latest_snapshot(rollout)

        self.assertEqual(snapshot.timestamp, "second")
        self.assertEqual(snapshot.context_window, 200)
        self.assertEqual(snapshot.last_input, 40)
        self.assertEqual(snapshot.last_uncached_input, 30)
        self.assertEqual(snapshot.primary_used_percent, 11.0)

    def test_json_includes_handoff_prompt_only_when_threshold_crossed(self):
        ok_payload = json.loads(snapshot_as_json(make_snapshot(10), 70, 85))
        urgent_payload = json.loads(snapshot_as_json(make_snapshot(90), 70, 85))

        self.assertIsNone(ok_payload["handoff_prompt"])
        self.assertIn("交接摘要", urgent_payload["handoff_prompt"])


if __name__ == "__main__":
    unittest.main()
