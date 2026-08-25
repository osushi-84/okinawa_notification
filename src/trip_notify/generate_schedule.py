from __future__ import annotations

import argparse
import random
import secrets
import sys
from pathlib import Path

from .config import load_config
from .errors import NotificationError
from .schedule import build_schedule, save_new_schedule
from .state import save_new_state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="通知スケジュールを1回だけ生成する")
    parser.add_argument("--config", type=Path, default=Path("config/production.json"))
    parser.add_argument("--output", type=Path, default=Path("data/notification_schedule.json"))
    parser.add_argument("--state", type=Path, default=Path("data/notification_state.json"))
    parser.add_argument("--force", action="store_true", help="既存のスケジュールと状態を再作成する")
    parser.add_argument("--show", action="store_true", help="生成した時刻一覧を明示的に表示する")
    parser.add_argument("--seed", type=int, help="テスト用の固定シード")
    return parser


def run(arguments: argparse.Namespace) -> None:
    if arguments.output.exists() != arguments.state.exists() and not arguments.force:
        raise NotificationError(
            "スケジュールと送信状態の片方だけが存在します。"
            "意図した再初期化であれば --force を指定してください"
        )
    config = load_config(arguments.config)
    rng = random.Random(arguments.seed) if arguments.seed is not None else secrets.SystemRandom()
    schedule = build_schedule(config, rng)
    digest = save_new_schedule(arguments.output, schedule, force=arguments.force)
    try:
        save_new_state(arguments.state, digest, force=arguments.force)
    except Exception:
        if not arguments.force:
            arguments.output.unlink(missing_ok=True)
        raise

    print(f"通知スケジュールを{len(schedule['notifications'])}件生成しました。")
    print(f"保存先: {arguments.output}")
    print("通常モードのため、通知予定時刻は表示していません。")
    if arguments.show:
        print("デバッグ表示:")
        for notification in schedule["notifications"]:
            print(
                f"  {notification['overall_index']:02d}: "
                f"{notification['scheduled_at']} "
                f"(今日 {notification['daily_index']}/{notification['daily_total']})"
            )


def main() -> int:
    try:
        run(build_parser().parse_args())
    except NotificationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
