from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .discord import credentials_from_environment, load_template, render_message, send_webhook
from .errors import NotificationError
from .schedule import load_schedule
from .state import load_state, mark_sent


def due_notifications(
    schedule: dict[str, Any], state: dict[str, Any], now: datetime
) -> list[dict[str, Any]]:
    if now.tzinfo is None or now.utcoffset() is None:
        raise NotificationError("現在時刻にタイムゾーンがありません")
    due: list[dict[str, Any]] = []
    for notification in schedule["notifications"]:
        scheduled_at = datetime.fromisoformat(notification["scheduled_at"])
        if scheduled_at <= now and notification["id"] not in state["sent"]:
            due.append(notification)
    return due


def process_due(
    schedule_path: Path,
    state_path: Path,
    template_path: Path,
    now: datetime,
    *,
    dry_run: bool = False,
    max_notifications: int | None = None,
    webhook_url: str | None = None,
    role_id: str | None = None,
    sender: Callable[[str, str, str], int] = send_webhook,
) -> int:
    schedule, schedule_digest = load_schedule(schedule_path)
    notification_ids = {item["id"] for item in schedule["notifications"]}
    state = load_state(state_path, schedule_digest, notification_ids)
    candidates = due_notifications(schedule, state, now)
    if max_notifications is not None:
        candidates = candidates[:max_notifications]

    if dry_run:
        print(f"送信対象: {len(candidates)}件（dry-runのため送信・状態更新なし）")
        return 0
    if not candidates:
        print("送信対象: 0件")
        return 0
    if webhook_url is None or role_id is None:
        webhook_url, role_id = credentials_from_environment()
    template = load_template(template_path)

    sent_count = 0
    for notification in candidates:
        content = render_message(template, notification, role_id)
        sender(webhook_url, content, role_id)
        # Webhook成功後にだけ、ローカルの状態を原子的に更新する。
        mark_sent(state_path, state, notification["id"], now)
        sent_count += 1
        print(
            f"送信成功: 全体 {notification['overall_index']} / "
            f"{notification['overall_total']}、今日 {notification['daily_index']} / "
            f"{notification['daily_total']}"
        )
    return sent_count


def parse_now(value: str | None, timezone: ZoneInfo) -> datetime:
    if value is None:
        return datetime.now(timezone)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise NotificationError("--nowはタイムゾーン付きISO 8601形式で指定してください") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise NotificationError("--nowには+09:00などのタイムゾーンが必要です")
    return parsed.astimezone(timezone)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="期限到来済みのDiscord通知を送信する")
    parser.add_argument("--schedule", type=Path, default=Path("data/notification_schedule.json"))
    parser.add_argument("--state", type=Path, default=Path("data/notification_state.json"))
    parser.add_argument("--template", type=Path, default=Path("config/discord_message.txt"))
    parser.add_argument("--now", help="デバッグ用の現在時刻（タイムゾーン付きISO 8601）")
    parser.add_argument("--dry-run", action="store_true", help="件数判定だけ行い、送信も状態更新もしない")
    parser.add_argument("--max-notifications", type=int, help="1度に送信する上限件数")
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        schedule, _ = load_schedule(arguments.schedule)
        timezone = ZoneInfo(schedule["timezone"])
        now = parse_now(arguments.now, timezone)
        if arguments.max_notifications is not None and arguments.max_notifications < 1:
            raise NotificationError("--max-notificationsは1以上で指定してください")
        process_due(
            arguments.schedule,
            arguments.state,
            arguments.template,
            now,
            dry_run=arguments.dry_run,
            max_notifications=arguments.max_notifications,
        )
    except NotificationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
