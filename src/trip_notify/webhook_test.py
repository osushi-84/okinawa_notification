from __future__ import annotations

import sys

from .discord import credentials_from_environment, send_webhook
from .errors import NotificationError


def main() -> int:
    try:
        webhook_url, role_id = credentials_from_environment()
        content = (
            f"<@&{role_id}>\n"
            "🧪 Discord Webhookの動作確認です。\n"
            "本番の通知状態には記録されません。"
        )
        send_webhook(webhook_url, content, role_id)
    except NotificationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("Webhookテスト送信に成功しました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
