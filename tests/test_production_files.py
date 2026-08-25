from pathlib import Path

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
