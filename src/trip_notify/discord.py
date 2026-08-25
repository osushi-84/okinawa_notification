from __future__ import annotations

import json
import os
import string
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .errors import NotificationError

ALLOWED_TEMPLATE_FIELDS = {
    "role_mention",
    "notification_id",
    "overall_index",
    "overall_total",
    "daily_index",
    "daily_total",
}


def load_template(path: Path) -> str:
    try:
        template = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise NotificationError(f"通知文テンプレートが見つかりません: {path}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise NotificationError(f"通知文テンプレートを読み込めません: {path}: {exc}") from exc
    if not template:
        raise NotificationError("通知文テンプレートが空です")
    try:
        fields = {
            field_name
            for _, field_name, _, _ in string.Formatter().parse(template)
            if field_name is not None
        }
    except ValueError as exc:
        raise NotificationError(f"通知文テンプレートの波括弧が不正です: {exc}") from exc
    unknown_fields = fields - ALLOWED_TEMPLATE_FIELDS
    if unknown_fields:
        raise NotificationError(
            "通知文テンプレートに未対応の変数があります: "
            + ", ".join(sorted(unknown_fields))
        )
    if "role_mention" not in fields:
        raise NotificationError("通知文テンプレートに {role_mention} が必要です")
    return template


def validate_role_id(role_id: str | None) -> str:
    if role_id is None or not role_id.isascii() or not role_id.isdecimal() or not 15 <= len(role_id) <= 25:
        raise NotificationError("DISCORD_ROLE_IDは15〜25桁の半角数字で登録してください")
    return role_id


def validate_webhook_url(webhook_url: str | None) -> str:
    if not webhook_url:
        raise NotificationError("DISCORD_WEBHOOK_URLが設定されていません")
    parsed = urllib.parse.urlparse(webhook_url)
    allowed_hosts = {"discord.com", "www.discord.com", "discordapp.com", "www.discordapp.com"}
    path_parts = [part for part in parsed.path.split("/") if part]
    if (
        parsed.scheme != "https"
        or parsed.hostname not in allowed_hosts
        or len(path_parts) < 4
        or path_parts[0:2] != ["api", "webhooks"]
    ):
        raise NotificationError("DISCORD_WEBHOOK_URLはDiscord公式のHTTPS Webhook URLである必要があります")
    return webhook_url


def render_message(template: str, notification: dict[str, Any], role_id: str) -> str:
    values = {
        "role_mention": f"<@&{role_id}>",
        "notification_id": notification["id"],
        "overall_index": notification["overall_index"],
        "overall_total": notification["overall_total"],
        "daily_index": notification["daily_index"],
        "daily_total": notification["daily_total"],
    }
    try:
        content = template.format_map(values)
    except (KeyError, ValueError) as exc:
        raise NotificationError(f"通知文テンプレートを展開できません: {exc}") from exc
    if len(content) > 2000:
        raise NotificationError("Discord通知文が2000文字を超えています")
    return content


def build_payload(content: str, role_id: str) -> dict[str, Any]:
    return {
        "content": content,
        "allowed_mentions": {
            "parse": [],
            "roles": [role_id],
            "users": [],
            "replied_user": False,
        },
    }


def _url_with_wait(webhook_url: str) -> str:
    parsed = urllib.parse.urlparse(webhook_url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(key, value) for key, value in query if key != "wait"]
    query.append(("wait", "true"))
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))


def send_webhook(
    webhook_url: str,
    content: str,
    role_id: str,
    *,
    timeout: float = 20.0,
    opener: Callable[..., Any] | None = None,
) -> int:
    webhook_url = validate_webhook_url(webhook_url)
    role_id = validate_role_id(role_id)
    payload = json.dumps(build_payload(content, role_id), ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        _url_with_wait(webhook_url),
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "okinawa-notification/1.0"},
    )
    open_request = opener or urllib.request.urlopen
    try:
        with open_request(request, timeout=timeout) as response:
            status = response.getcode()
    except urllib.error.HTTPError as exc:
        raise NotificationError(f"Discord送信に失敗しました (HTTP {exc.code})") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise NotificationError(f"Discord送信に失敗しました ({type(exc).__name__})") from exc
    if not 200 <= status < 300:
        raise NotificationError(f"Discord送信に失敗しました (HTTP {status})")
    return status


def credentials_from_environment() -> tuple[str, str]:
    webhook_url = validate_webhook_url(os.environ.get("DISCORD_WEBHOOK_URL"))
    role_id = validate_role_id(os.environ.get("DISCORD_ROLE_ID"))
    return webhook_url, role_id
