from pathlib import Path

from trip_notify.discord import load_template
from trip_notify.schedule import load_schedule
from trip_notify.state import load_state
from trip_notify.validate import validate_production_files


def test_committed_production_files_are_consistent() -> None:
    count = validate_production_files(
        Path("config/production.json"),
        Path("data/notification_schedule.json"),
        Path("data/notification_state.json"),
        Path("config/discord_message.txt"),
    )

    # 依頼文の日別回数 3 + 8 + 8 + 2 を優先した結果。
    assert count == 21


def test_one_time_2300_test_files_are_consistent() -> None:
    schedule, digest = load_schedule(Path("data/one_time_test_schedule.json"))
    ids = {item["id"] for item in schedule["notifications"]}
    state = load_state(Path("data/one_time_test_state.json"), digest, ids)
    template = load_template(Path("config/one_time_test_message.txt"))

    assert len(schedule["notifications"]) == 1
    assert schedule["notifications"][0]["scheduled_at"] == "2026-08-25T23:00:00+09:00"
    assert state["sent"] == {}
    assert "{role_mention}" in template
