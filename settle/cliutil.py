"""CLI 입력 파싱 도우미."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from typing import Optional

from .models import POT_ID, POT_NAME, Payment, Trip
from .money import to_minor


class InputError(Exception):
    """사용자 입력이 잘못됐을 때."""


def parse_day(text: Optional[str], default_year: Optional[int] = None) -> Optional[date]:
    if not text:
        return None
    value = text.strip().lower()
    today = date.today()
    if value in ("오늘", "today", "t"):
        return today
    if value in ("어제", "yesterday", "y"):
        return today - timedelta(days=1)
    if value in ("내일", "tomorrow"):
        return today + timedelta(days=1)
    year = default_year or today.year
    cleaned = value.replace(".", "-").replace("/", "-")
    parts = [p for p in cleaned.split("-") if p]
    try:
        if len(parts) == 3:
            y, m, d = parts
            if len(y) == 2:
                y = "20" + y
            return date(int(y), int(m), int(d))
        if len(parts) == 2:
            return date(year, int(parts[0]), int(parts[1]))
    except ValueError:
        pass
    raise InputError(f"날짜를 해석할 수 없습니다: {text} (예: 2025-08-29, 08-29, 오늘)")


def resolve_entity(trip: Trip, name: str) -> str:
    """멤버 이름 또는 '공금'을 id로."""
    key = name.strip()
    if key in (POT_ID, POT_NAME, "공금", "회비", "pot"):
        return POT_ID
    return trip.resolve_member(key).id


def parse_payers(trip: Trip, spec: str, amount: int, currency: str) -> list[Payment]:
    """'민수' / '민수:60000,지영:30000' / '공금' 을 결제 목록으로.

    금액을 하나만 생략하면 나머지를 자동으로 채운다.
    """
    spec = (spec or "").strip()
    if not spec:
        raise InputError("결제한 사람을 지정하세요")
    entries: list[tuple[str, Optional[int]]] = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" in chunk or "=" in chunk:
            separator = ":" if ":" in chunk else "="
            name, raw = chunk.split(separator, 1)
            entries.append((resolve_entity(trip, name), to_minor(raw, currency)))
        else:
            entries.append((resolve_entity(trip, chunk), None))
    if not entries:
        raise InputError("결제한 사람을 지정하세요")

    missing = [i for i, (_, value) in enumerate(entries) if value is None]
    known = sum(value for _, value in entries if value is not None)
    if not missing:
        if known != amount:
            raise InputError(
                f"결제액 합계({known:,})가 지출 금액({amount:,})과 다릅니다"
            )
    elif len(missing) == 1:
        entries[missing[0]] = (entries[missing[0]][0], amount - known)
    else:
        # 금액을 하나도 안 적었으면 균등하게 나눠 결제한 것으로 본다
        from .money import allocate

        shares = allocate(amount - known, [1] * len(missing))
        for index, share in zip(missing, shares):
            entries[index] = (entries[index][0], share)
    return [Payment(member_id=mid, amount=value or 0) for mid, value in entries]


def parse_members(trip: Trip, spec: Optional[str]) -> list[str]:
    if not spec:
        return []
    return [trip.resolve_member(name).id for name in spec.split(",") if name.strip()]


def parse_values(trip: Trip, spec: Optional[str]) -> dict[str, float]:
    """'민수=2,지영=1' -> {member_id: value}"""
    result: dict[str, float] = {}
    if not spec:
        return result
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            raise InputError(f"'이름=값' 형식이어야 합니다: {chunk}")
        name, raw = chunk.split("=", 1)
        result[trip.resolve_member(name).id] = float(raw.strip())
    return result


def parse_amounts(trip: Trip, spec: Optional[str], currency: str) -> dict[str, int]:
    """'민수=20000,지영=5000' -> {member_id: 최소단위 금액}"""
    result: dict[str, int] = {}
    if not spec:
        return result
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            raise InputError(f"'이름=금액' 형식이어야 합니다: {chunk}")
        name, raw = chunk.split("=", 1)
        result[trip.resolve_member(name).id] = to_minor(raw, currency)
    return result


def ask(prompt: str, default: str = "", required: bool = False) -> str:
    """대화형 질문. 파이프로 실행 중이면 기본값을 그대로 쓴다."""
    if not sys.stdin.isatty():
        return default
    suffix = f" [{default}]" if default else ""
    while True:
        answer = input(f"{prompt}{suffix}: ").strip()
        if not answer:
            answer = default
        if answer or not required:
            return answer
        print("  값을 입력하세요.")


def confirm(prompt: str, default: bool = True) -> bool:
    if not sys.stdin.isatty():
        return default
    hint = "Y/n" if default else "y/N"
    answer = input(f"{prompt} ({hint}): ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes", "ㅇ", "네")
