"""저장소. 여행 장부를 JSON 파일 하나로 보관한다."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .models import Book, migrate

ENV_PATH = "TRAVEL_SETTLE_DATA"
DEFAULT_PATH = Path.home() / ".travel-settle" / "data.json"


def default_path() -> Path:
    override = os.environ.get(ENV_PATH)
    return Path(override).expanduser() if override else DEFAULT_PATH


def load(path: Path | None = None) -> Book:
    target = Path(path) if path else default_path()
    if not target.exists():
        return Book()
    with target.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return Book.from_dict(migrate(raw))


def save(book: Book, path: Path | None = None) -> Path:
    target = Path(path) if path else default_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        backup = target.with_suffix(target.suffix + ".bak")
        shutil.copy2(target, backup)
    temp = target.with_suffix(target.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as fh:
        json.dump(book.to_dict(), fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(temp, target)  # 원자적 교체: 쓰다가 죽어도 원본이 남는다
    return target


def export_json(book: Book, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(book.to_dict(), fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return path


def import_json(path: Path) -> Book:
    with Path(path).open("r", encoding="utf-8") as fh:
        return Book.from_dict(migrate(json.load(fh)))
