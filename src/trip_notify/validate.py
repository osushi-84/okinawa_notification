from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from .config import load_config
from .discord import load_template
from .errors import NotificationError
from .schedule import load_schedule
from .state import load_state


def validate_production_files(
    config_path: Path, schedule_path: Path, state_path: Path, template_path: Path
) -> int:
    config = load_config(config_path)
    schedule, schedule_digest = load_schedule(schedule_path)
    if schedule.get("config_sha256") != config.sha256:
        raise NotificationError("本番設定と生成済み通知スケジュールが一致しません")
    if schedule.get("timezone") != config.timezone_name:
        raise NotificationError("本番設定と通知スケジュールのタイムゾーンが一致しません")

    notifications = schedule["notifications"]
    expected_total = sum(day.count for day in config.days)
    if len(notifications) != expected_total:
        raise NotificationError(f"通知件数が設定と異なります（期待: {expected_total}）")

    position = 0
    for day in config.days:
        day_notifications = notifications[position : position + day.count]
        position += day.count
        if len(day_notifications) != day.count:
            raise NotificationError(f"{day.date}: 通知件数が不正です")
        start, end = day.bounds(config.timezone)
        previous: datetime | None = None
        for daily_index, notification in enumerate(day_notifications, start=1):
            scheduled_at = datetime.fromisoformat(notification["scheduled_at"]).astimezone(config.timezone)
            if not start <= scheduled_at < end:
                raise NotificationError(f"{day.date}: 通知時刻が設定時間帯の範囲外です")
            elapsed_minutes = int((scheduled_at - start).total_seconds() // 60)
            if elapsed_minutes % config.slot_minutes:
                raise NotificationError(f"{day.date}: 通知時刻が{config.slot_minutes}分単位ではありません")
            if previous is not None and scheduled_at - previous < timedelta(
                minutes=config.minimum_interval_minutes
            ):
                raise NotificationError(f"{day.date}: 通知間隔が最小値未満です")
            if notification["daily_index"] != daily_index or notification["daily_total"] != day.count:
                raise NotificationError(f"{day.date}: 日内連番または日内総数が不正です")
            previous = scheduled_at

    ids = {notification["id"] for notification in notifications}
    load_state(state_path, schedule_digest, ids)
    load_template(template_path)
    return expected_total


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="本番用の設定・スケジュール・状態を検証する")
    parser.add_argument("--config", type=Path, default=Path("config/production.json"))
    parser.add_argument("--schedule", type=Path, default=Path("data/notification_schedule.json"))
    parser.add_argument("--state", type=Path, default=Path("data/notification_state.json"))
    parser.add_argument("--template", type=Path, default=Path("config/discord_message.txt"))
    parser.add_argument("--show", action="store_true", help="デバッグ用に通知予定時刻を表示する")
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        count = validate_production_files(
            arguments.config, arguments.schedule, arguments.state, arguments.template
        )
    except NotificationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"検証成功: 通知{count}件（予定時刻は非表示）")
    if arguments.show:
        schedule, _ = load_schedule(arguments.schedule)
        print("デバッグ表示:")
        for notification in schedule["notifications"]:
            print(
                f"  {notification['overall_index']:02d}: "
                f"{notification['scheduled_at']} "
                f"(今日 {notification['daily_index']}/{notification['daily_total']})"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
