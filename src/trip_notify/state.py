from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import NotificationError
from .files import read_json, write_json_atomic


def new_state(schedule_sha256: str) -> dict[str, Any]:
    return {"version": 1, "schedule_sha256": schedule_sha256, "sent": {}}


def save_new_state(path: Path, schedule_sha256: str, force: bool = False) -> None:
    if path.exists() and not force:
        raise NotificationError(
            f"送信状態は既に存在します。再初期化する場合だけ --force を指定してください: {path}"
        )
    write_json_atomic(path, new_state(schedule_sha256))


def load_state(
    path: Path, schedule_sha256: str, valid_notification_ids: set[str]
) -> dict[str, Any]:
    state, _ = read_json(path, "送信状態")
    if state.get("version") != 1:
        raise NotificationError("送信状態のversionは1である必要があります")
    if state.get("schedule_sha256") != schedule_sha256:
        raise NotificationError(
            "送信状態が現在の通知スケジュールと一致しません。"
            "スケジュールを再生成した場合は状態も明示的に初期化してください"
        )
    sent = state.get("sent")
    if not isinstance(sent, dict):
        raise NotificationError("送信状態のsentはJSONオブジェクトである必要があります")
    unknown_ids = set(sent) - valid_notification_ids
    if unknown_ids:
        raise NotificationError("送信状態に未知の通知IDが含まれています")
    for notification_id, details in sent.items():
        if not isinstance(details, dict) or not isinstance(details.get("sent_at"), str):
            raise NotificationError(f"通知ID {notification_id} の送信状態が不正です")
    return state


def mark_sent(
    state_path: Path,
    state: dict[str, Any],
    notification_id: str,
    sent_at: datetime,
) -> None:
    if notification_id in state["sent"]:
        raise NotificationError(f"通知ID {notification_id} はすでに送信済みです")
    state["sent"][notification_id] = {"sent_at": sent_at.isoformat()}
    write_json_atomic(state_path, state)
