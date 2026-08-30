"""저장소. 여행 장부를 JSON 파일 하나로 보관한다."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Optional

from .models import Book, migrate

ENV_PATH = "TRAVEL_SETTLE_DATA"
HOME_DIR = Path.home() / ".travel-settle"
DEFAULT_PATH = HOME_DIR / "data.json"
CONFIG_PATH = HOME_DIR / "config.json"


def load_config() -> dict:
    """설정 파일. 지금은 장부 위치 하나만 담는다."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}          # 설정이 깨졌다고 프로그램이 못 뜨면 곤란하다


def save_config(config: dict) -> Path:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = CONFIG_PATH.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as fh:
        json.dump(config, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(temp, CONFIG_PATH)
    return CONFIG_PATH


def configured_path() -> Optional[Path]:
    raw = load_config().get("data_path")
    return Path(str(raw)).expanduser() if raw else None


def default_path() -> Path:
    """장부 위치. 우선순위는 --data > 환경변수 > 설정 파일 > 홈 디렉터리."""
    override = os.environ.get(ENV_PATH)
    if override:
        return Path(override).expanduser()
    configured = configured_path()
    return configured if configured else DEFAULT_PATH


def describe_paths(cli_override: Optional[Path] = None) -> list[tuple[str, str]]:
    """지금 어디를 쓰는지, 왜 그런지 사람이 볼 수 있게."""
    rows = []
    if cli_override:
        rows.append(("--data 옵션", str(cli_override)))
    env = os.environ.get(ENV_PATH)
    if env:
        rows.append((f"환경변수 {ENV_PATH}", env))
    configured = load_config().get("data_path")
    rows.append(("설정 파일", str(configured) if configured else "(지정 안 됨)"))
    rows.append(("기본 위치", str(DEFAULT_PATH)))
    return rows


def images_dir(path: Path | None = None) -> Path:
    """장부 옆에 캡쳐 이미지를 모아 둔다. 지출에서 원본을 되짚을 수 있게."""
    target = (Path(path) if path else default_path()).parent / "images"
    target.mkdir(parents=True, exist_ok=True)
    return target


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
