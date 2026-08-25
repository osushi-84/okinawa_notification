from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from trip_notify.config import load_config
from trip_notify.errors import NotificationError
from trip_notify.schedule import build_schedule, choose_spaced_slots, save_new_schedule


def write_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "timezone": "Asia/Tokyo",
                "slot_minutes": 5,
                "minimum_interval_minutes": 45,
                "days": [
                    {"date": "2026-08-28", "start": "17:00", "end": "24:00", "count": 3},
                    {"date": "2026-08-29", "start": "07:00", "end": "24:00", "count": 8},
                ],
            }
        ),
        encoding="utf-8",
    )


def test_build_schedule_obeys_counts_slots_and_minimum_interval(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    write_config(config_path)
    config = load_config(config_path)

    schedule = build_schedule(config, random.Random(1234))

    assert len(schedule["notifications"]) == 11
    first_day = schedule["notifications"][:3]
    second_day = schedule["notifications"][3:]
    assert [item["daily_index"] for item in first_day] == [1, 2, 3]
    assert [item["daily_index"] for item in second_day] == list(range(1, 9))
    for group in (first_day, second_day):
        times = [datetime.fromisoformat(item["scheduled_at"]) for item in group]
        assert all(value.minute % 5 == 0 for value in times)
        assert all(later - earlier >= timedelta(minutes=45) for earlier, later in zip(times, times[1:]))
    assert all(item["overall_total"] == 11 for item in schedule["notifications"])


def test_choose_spaced_slots_rejects_impossible_request() -> None:
    start = datetime.fromisoformat("2026-08-28T17:00:00+09:00")
    candidates = [start + timedelta(minutes=5 * index) for index in range(3)]

    with pytest.raises(NotificationError, match="配置できません"):
        choose_spaced_slots(candidates, 2, timedelta(minutes=45), random.Random(1))


def test_save_new_schedule_refuses_accidental_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "schedule.json"
    schedule = {"version": 1}
    save_new_schedule(output, schedule)

    with pytest.raises(NotificationError, match="既に存在"):
        save_new_schedule(output, schedule)
