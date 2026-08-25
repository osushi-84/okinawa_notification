from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import NotificationError
from .files import read_json


@dataclass(frozen=True)
class DayConfig:
    date: date
    start_text: str
    end_text: str
    count: int

    def bounds(self, timezone: ZoneInfo) -> tuple[datetime, datetime]:
        start = _parse_clock(self.start_text, self.date, timezone, allow_24=False)
        end = _parse_clock(self.end_text, self.date, timezone, allow_24=True)
        if end <= start:
            raise NotificationError(f"{self.date}: endはstartより後である必要があります")
        return start, end


@dataclass(frozen=True)
class ProductionConfig:
    timezone_name: str
    timezone: ZoneInfo
    slot_minutes: int
    minimum_interval_minutes: int
    days: tuple[DayConfig, ...]
    sha256: str


def _require_int(value: Any, field: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise NotificationError(f"{field}は{minimum}以上の整数である必要があります")
    return value


def _parse_clock(value: str, target_date: date, timezone: ZoneInfo, allow_24: bool) -> datetime:
    if allow_24 and value == "24:00":
        return datetime.combine(target_date + timedelta(days=1), time.min, timezone)
    try:
        parsed = time.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise NotificationError(f"時刻はHH:MM形式で指定してください: {value!r}") from exc
    if parsed.second or parsed.microsecond or parsed.tzinfo is not None:
        raise NotificationError(f"時刻はHH:MM形式で指定してください: {value!r}")
    return datetime.combine(target_date, parsed, timezone)


def load_config(path: Path) -> ProductionConfig:
    raw, digest = read_json(path, "本番設定")
    if raw.get("version") != 1:
        raise NotificationError("本番設定のversionは1である必要があります")

    timezone_name = raw.get("timezone")
    if not isinstance(timezone_name, str):
        raise NotificationError("本番設定のtimezoneが不正です")
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise NotificationError(f"未対応のタイムゾーンです: {timezone_name}") from exc

    slot_minutes = _require_int(raw.get("slot_minutes"), "slot_minutes")
    minimum_interval_minutes = _require_int(
        raw.get("minimum_interval_minutes"), "minimum_interval_minutes"
    )
    raw_days = raw.get("days")
    if not isinstance(raw_days, list) or not raw_days:
        raise NotificationError("daysは1件以上の配列である必要があります")

    days: list[DayConfig] = []
    seen_dates: set[date] = set()
    for index, raw_day in enumerate(raw_days, start=1):
        if not isinstance(raw_day, dict):
            raise NotificationError(f"days[{index}]はJSONオブジェクトである必要があります")
        try:
            target_date = date.fromisoformat(raw_day.get("date"))
        except (TypeError, ValueError) as exc:
            raise NotificationError(f"days[{index}].dateはYYYY-MM-DD形式で指定してください") from exc
        if target_date in seen_dates:
            raise NotificationError(f"日付が重複しています: {target_date}")
        seen_dates.add(target_date)
        start_text = raw_day.get("start")
        end_text = raw_day.get("end")
        if not isinstance(start_text, str) or not isinstance(end_text, str):
            raise NotificationError(f"days[{index}]のstart/endは文字列で指定してください")
        day = DayConfig(
            date=target_date,
            start_text=start_text,
            end_text=end_text,
            count=_require_int(raw_day.get("count"), f"days[{index}].count"),
        )
        start, end = day.bounds(timezone)
        duration_minutes = int((end - start).total_seconds() // 60)
        if duration_minutes < 1:
            raise NotificationError(f"{target_date}: 通知時間帯が短すぎます")
        days.append(day)

    days.sort(key=lambda item: item.date)
    return ProductionConfig(
        timezone_name=timezone_name,
        timezone=timezone,
        slot_minutes=slot_minutes,
        minimum_interval_minutes=minimum_interval_minutes,
        days=tuple(days),
        sha256=digest,
    )
