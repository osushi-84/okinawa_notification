from __future__ import annotations

import bisect
import random
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import DayConfig, ProductionConfig
from .errors import NotificationError
from .files import read_json, sha256_bytes, write_json_atomic


class RandomSource(Protocol):
    def randrange(self, stop: int) -> int: ...


def _candidate_slots(day: DayConfig, config: ProductionConfig) -> list[datetime]:
    start, end = day.bounds(config.timezone)
    slots: list[datetime] = []
    current = start
    step = timedelta(minutes=config.slot_minutes)
    while current < end:
        slots.append(current)
        current += step
    return slots


def choose_spaced_slots(
    candidates: list[datetime], count: int, minimum_interval: timedelta, rng: RandomSource
) -> list[datetime]:
    """最小間隔を満たす組合せから、偏りなく1組を選ぶ。"""
    if count < 1:
        raise NotificationError("通知回数は1以上である必要があります")
    if not candidates:
        raise NotificationError("通知候補時刻がありません")

    next_indices = [
        bisect.bisect_left(candidates, candidate + minimum_interval)
        for candidate in candidates
    ]

    @lru_cache(maxsize=None)
    def number_of_ways(index: int, remaining: int) -> int:
        if remaining == 0:
            return 1
        if index >= len(candidates):
            return 0
        without_current = number_of_ways(index + 1, remaining)
        with_current = number_of_ways(next_indices[index], remaining - 1)
        return without_current + with_current

    total_ways = number_of_ways(0, count)
    if total_ways == 0:
        raise NotificationError(
            f"指定時間帯に最小間隔を保って{count}件配置できません"
        )

    selected: list[datetime] = []
    index = 0
    remaining = count
    while remaining:
        with_current = number_of_ways(next_indices[index], remaining - 1)
        without_current = number_of_ways(index + 1, remaining)
        draw = rng.randrange(with_current + without_current)
        if draw < with_current:
            selected.append(candidates[index])
            index = next_indices[index]
            remaining -= 1
        else:
            index += 1
    return selected


def build_schedule(config: ProductionConfig, rng: RandomSource) -> dict[str, Any]:
    notifications: list[dict[str, Any]] = []
    overall_index = 1
    overall_total = sum(day.count for day in config.days)
    minimum_interval = timedelta(minutes=config.minimum_interval_minutes)

    for day in config.days:
        selected = choose_spaced_slots(
            _candidate_slots(day, config), day.count, minimum_interval, rng
        )
        for daily_index, scheduled_at in enumerate(selected, start=1):
            notifications.append(
                {
                    "id": f"notification-{overall_index:02d}",
                    "scheduled_at": scheduled_at.isoformat(),
                    "overall_index": overall_index,
                    "overall_total": overall_total,
                    "daily_index": daily_index,
                    "daily_total": day.count,
                }
            )
            overall_index += 1

    return {
        "version": 1,
        "timezone": config.timezone_name,
        "config_sha256": config.sha256,
        "notifications": notifications,
    }


def load_schedule(path: Path) -> tuple[dict[str, Any], str]:
    schedule, digest = read_json(path, "通知スケジュール")
    if schedule.get("version") != 1:
        raise NotificationError("通知スケジュールのversionは1である必要があります")
    timezone_name = schedule.get("timezone")
    try:
        timezone = ZoneInfo(timezone_name)
    except (TypeError, ZoneInfoNotFoundError) as exc:
        raise NotificationError("通知スケジュールのtimezoneが不正です") from exc
    raw_notifications = schedule.get("notifications")
    if not isinstance(raw_notifications, list) or not raw_notifications:
        raise NotificationError("通知スケジュールのnotificationsが不正です")

    ids: set[str] = set()
    previous_time: datetime | None = None
    expected_total = len(raw_notifications)
    for expected_index, notification in enumerate(raw_notifications, start=1):
        if not isinstance(notification, dict):
            raise NotificationError(f"通知{expected_index}件目がJSONオブジェクトではありません")
        notification_id = notification.get("id")
        if not isinstance(notification_id, str) or not notification_id or notification_id in ids:
            raise NotificationError(f"通知{expected_index}件目のidが不正または重複しています")
        ids.add(notification_id)
        try:
            scheduled_at = datetime.fromisoformat(notification.get("scheduled_at"))
        except (TypeError, ValueError) as exc:
            raise NotificationError(f"通知{expected_index}件目のscheduled_atが不正です") from exc
        if scheduled_at.tzinfo is None or scheduled_at.utcoffset() is None:
            raise NotificationError(f"通知{expected_index}件目のscheduled_atにタイムゾーンがありません")
        if scheduled_at.astimezone(timezone).utcoffset() != scheduled_at.utcoffset():
            raise NotificationError(f"通知{expected_index}件目のscheduled_atがtimezoneと一致しません")
        if previous_time is not None and scheduled_at <= previous_time:
            raise NotificationError("通知スケジュールは時刻の昇順である必要があります")
        previous_time = scheduled_at
        for field in ("overall_index", "overall_total", "daily_index", "daily_total"):
            value = notification.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise NotificationError(f"通知{expected_index}件目の{field}が不正です")
        if notification["overall_index"] != expected_index:
            raise NotificationError("通知のoverall_indexが連番ではありません")
        if notification["overall_total"] != expected_total:
            raise NotificationError("通知のoverall_totalが件数と一致しません")
    return schedule, digest


def save_new_schedule(path: Path, schedule: dict[str, Any], force: bool = False) -> str:
    if path.exists() and not force:
        raise NotificationError(
            f"通知スケジュールは既に存在します。再生成する場合だけ --force を指定してください: {path}"
        )
    write_json_atomic(path, schedule)
    return sha256_bytes(path.read_bytes())
