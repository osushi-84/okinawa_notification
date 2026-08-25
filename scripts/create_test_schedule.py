from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from trip_notify.errors import NotificationError
from trip_notify.schedule import save_new_schedule
from trip_notify.state import save_new_state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="現在時刻からの相対分で、本番と分離したテスト予定を作る"
    )
    parser.add_argument("--minutes", type=int, nargs="+", default=[5, 10])
    parser.add_argument("--timezone", default="Asia/Tokyo")
    parser.add_argument("--output", type=Path, default=Path("tmp/test_notification_schedule.json"))
    parser.add_argument("--state", type=Path, default=Path("tmp/test_notification_state.json"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--show", action="store_true", help="テスト予定時刻を表示する")
    return parser


def run(arguments: argparse.Namespace) -> None:
    if any(minutes < 0 for minutes in arguments.minutes):
        raise NotificationError("--minutesは0以上で指定してください")
    if len(set(arguments.minutes)) != len(arguments.minutes):
        raise NotificationError("--minutesに同じ値を重複して指定できません")
    try:
        timezone = ZoneInfo(arguments.timezone)
    except ZoneInfoNotFoundError as exc:
        raise NotificationError(f"未対応のタイムゾーンです: {arguments.timezone}") from exc

    base = datetime.now(timezone).replace(second=0, microsecond=0)
    scheduled_times = [base + timedelta(minutes=value) for value in sorted(arguments.minutes)]
    counts_by_date: dict[object, int] = {}
    for scheduled_at in scheduled_times:
        counts_by_date[scheduled_at.date()] = counts_by_date.get(scheduled_at.date(), 0) + 1
    daily_positions: dict[object, int] = {}
    notifications = []
    total = len(scheduled_times)
    for overall_index, scheduled_at in enumerate(scheduled_times, start=1):
        target_date = scheduled_at.date()
        daily_positions[target_date] = daily_positions.get(target_date, 0) + 1
        notifications.append(
            {
                "id": f"test-notification-{overall_index:02d}",
                "scheduled_at": scheduled_at.isoformat(),
                "overall_index": overall_index,
                "overall_total": total,
                "daily_index": daily_positions[target_date],
                "daily_total": counts_by_date[target_date],
            }
        )
    schedule = {
        "version": 1,
        "timezone": arguments.timezone,
        "test_schedule": True,
        "notifications": notifications,
    }
    digest = save_new_schedule(arguments.output, schedule, force=arguments.force)
    save_new_state(arguments.state, digest, force=arguments.force)
    print(f"テスト通知スケジュールを{total}件生成しました: {arguments.output}")
    if arguments.show:
        for notification in notifications:
            print(f"  {notification['overall_index']:02d}: {notification['scheduled_at']}")


def main() -> int:
    try:
        run(build_parser().parse_args())
    except NotificationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
