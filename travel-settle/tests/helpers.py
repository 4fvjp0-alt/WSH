"""테스트 공통 도우미."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from settle.models import Expense, Member, Payment, Trip  # noqa: E402


def make_trip(names=("민수", "지영", "현우"), **kwargs) -> Trip:
    trip = Trip(
        id="t", name="테스트 여행", base_currency=kwargs.pop("base_currency", "KRW"),
        start=kwargs.pop("start", date(2025, 5, 1)),
        end=kwargs.pop("end", date(2025, 5, 4)),
        members=[Member(id=f"m{i}", name=name) for i, name in enumerate(names)],
        **kwargs,
    )
    return trip


def ids(trip: Trip) -> dict[str, str]:
    return {m.name: m.id for m in trip.members}


def expense(eid: str, amount: int, payer, **kwargs) -> Expense:
    if isinstance(payer, str):
        payments = [Payment(payer, amount)]
    else:
        payments = list(payer)
    return Expense(id=eid, title=kwargs.pop("title", eid), amount=amount,
                   payments=payments, **kwargs)
