from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .errors import NotificationError


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def read_json(path: Path, label: str) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise NotificationError(f"{label}が見つかりません: {path}") from exc
    except OSError as exc:
        raise NotificationError(f"{label}を読み込めません: {path}: {exc}") from exc

    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NotificationError(
            f"{label}が正しいUTF-8 JSONではありません: {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise NotificationError(f"{label}のルートはJSONオブジェクトである必要があります: {path}")
    return value, sha256_bytes(raw)


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
        ) as temporary:
            temporary.write(serialized)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        os.replace(temporary_name, path)
    except OSError as exc:
        if temporary_name:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass
        raise NotificationError(f"JSONファイルを安全に保存できません: {path}: {exc}") from exc
