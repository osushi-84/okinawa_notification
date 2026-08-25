from __future__ import annotations

import json
from pathlib import Path

import pytest

from trip_notify.discord import load_template, send_webhook, validate_webhook_url
from trip_notify.errors import NotificationError


class FakeResponse:
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def getcode(self) -> int:
        return 200


def test_payload_allows_only_configured_role() -> None:
    captured: dict[str, object] = {}

    def opener(request: object, timeout: float) -> FakeResponse:
        captured["url"] = request.full_url  # type: ignore[attr-defined]
        captured["payload"] = json.loads(request.data)  # type: ignore[attr-defined]
        return FakeResponse()

    send_webhook(
        "https://discord.com/api/webhooks/123/secret-token",
        "<@&123456789012345678> @everyone",
        "123456789012345678",
        opener=opener,
    )

    payload = captured["payload"]
    assert payload["allowed_mentions"] == {  # type: ignore[index]
        "parse": [],
        "roles": ["123456789012345678"],
        "users": [],
        "replied_user": False,
    }
    assert "wait=true" in captured["url"]  # type: ignore[operator]


def test_non_discord_webhook_url_is_rejected() -> None:
    with pytest.raises(NotificationError, match="Discord公式"):
        validate_webhook_url("https://example.com/api/webhooks/123/token")


def test_template_requires_role_mention(tmp_path: Path) -> None:
    template = tmp_path / "message.txt"
    template.write_text("📸 {overall_index}", encoding="utf-8")

    with pytest.raises(NotificationError, match="role_mention"):
        load_template(template)


def test_template_rejects_unknown_placeholder(tmp_path: Path) -> None:
    template = tmp_path / "message.txt"
    template.write_text("{role_mention} {secret}", encoding="utf-8")

    with pytest.raises(NotificationError, match="未対応"):
        load_template(template)
