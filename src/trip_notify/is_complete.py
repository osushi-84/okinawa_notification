from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .errors import NotificationError
from .schedule import load_schedule
from .state import load_state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="全通知の送信完了を確認する")
    parser.add_argument("--schedule", type=Path, default=Path("data/notification_schedule.json"))
    parser.add_argument("--state", type=Path, default=Path("data/notification_state.json"))
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        schedule, digest = load_schedule(arguments.schedule)
        ids = {item["id"] for item in schedule["notifications"]}
        state = load_state(arguments.state, digest, ids)
    except NotificationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    sent_count = len(state["sent"])
    total = len(ids)
    if sent_count == total:
        print(f"全通知の送信が完了しました（{sent_count} / {total}）。")
        return 0
    print(f"未完了: 送信済み {sent_count} / {total}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
