from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from trip_notify.errors import NotificationError
from trip_notify.files import read_json, write_json_atomic
from trip_notify.schedule import save_new_schedule
from trip_notify.send_due import process_due
from trip_notify.state import load_state, save_new_state


def create_runtime_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    schedule_path = tmp_path / "schedule.json"
    state_path = tmp_path / "state.json"
    template_path = tmp_path / "message.txt"
    schedule = {
        "version": 1,
        "timezone": "Asia/Tokyo",
        "notifications": [
            {
                "id": "notification-01",
                "scheduled_at": "2026-08-28T17:00:00+09:00",
                "overall_index": 1,
                "overall_total": 2,
                "daily_index": 1,
                "daily_total": 2,
            },
            {
                "id": "notification-02",
                "scheduled_at": "2026-08-28T18:00:00+09:00",
                "overall_index": 2,
                "overall_total": 2,
                "daily_index": 2,
                "daily_total": 2,
            },
        ],
    }
    digest = save_new_schedule(schedule_path, schedule)
    save_new_state(state_path, digest)
    template_path.write_text(
        "{role_mention} {overall_index}/{overall_total} {daily_index}/{daily_total}",
        encoding="utf-8",
    )
    return schedule_path, state_path, template_path


def test_success_is_persisted_and_not_sent_twice(tmp_path: Path) -> None:
    schedule_path, state_path, template_path = create_runtime_files(tmp_path)
    sent_contents: list[str] = []

    def fake_sender(url: str, content: str, role_id: str) -> int:
        sent_contents.append(content)
        return 200

    now = datetime(2026, 8, 28, 17, 30, tzinfo=ZoneInfo("Asia/Tokyo"))
    first_count = process_due(
        schedule_path,
        state_path,
        template_path,
        now,
        webhook_url="https://discord.com/api/webhooks/123/token",
        role_id="123456789012345678",
        sender=fake_sender,
    )
    second_count = process_due(
        schedule_path,
        state_path,
        template_path,
        now,
        webhook_url="https://discord.com/api/webhooks/123/token",
        role_id="123456789012345678",
        sender=fake_sender,
    )

    assert first_count == 1
    assert second_count == 0
    assert len(sent_contents) == 1
    assert "<@&123456789012345678>" in sent_contents[0]


def test_failure_does_not_change_state(tmp_path: Path) -> None:
    schedule_path, state_path, template_path = create_runtime_files(tmp_path)
    before = state_path.read_bytes()

    def failing_sender(url: str, content: str, role_id: str) -> int:
        raise NotificationError("送信失敗")

    with pytest.raises(NotificationError, match="送信失敗"):
        process_due(
            schedule_path,
            state_path,
            template_path,
            datetime(2026, 8, 28, 17, 30, tzinfo=ZoneInfo("Asia/Tokyo")),
            webhook_url="https://discord.com/api/webhooks/123/token",
            role_id="123456789012345678",
            sender=failing_sender,
        )

    assert state_path.read_bytes() == before


def test_dry_run_needs_no_discord_credentials_and_keeps_state(tmp_path: Path) -> None:
    schedule_path, state_path, template_path = create_runtime_files(tmp_path)
    before = state_path.read_bytes()

    count = process_due(
        schedule_path,
        state_path,
        template_path,
        datetime(2026, 8, 28, 19, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
        dry_run=True,
    )

    assert count == 0
    assert state_path.read_bytes() == before


def test_corrupt_state_has_clear_error(tmp_path: Path) -> None:
    schedule_path, state_path, _ = create_runtime_files(tmp_path)
    state_path.write_text("{broken", encoding="utf-8")

    with pytest.raises(NotificationError, match="正しいUTF-8 JSON"):
        load_state(state_path, "unused", {"notification-01", "notification-02"})


def test_schedule_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    schedule_path, state_path, _ = create_runtime_files(tmp_path)
    state, _ = read_json(state_path, "state")
    state["schedule_sha256"] = "0" * 64
    write_json_atomic(state_path, state)

    with pytest.raises(NotificationError, match="スケジュールと一致"):
        load_state(state_path, "f" * 64, {"notification-01", "notification-02"})
