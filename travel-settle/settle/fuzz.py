"""무작위 여행 생성기.

폐루프 검증의 재료다. 사람이 만들 법한 모든 조합(다중 결제자, 부분 참여,
환불, 조정액, 공금, 다중 통화, 반올림)을 무작위로 섞은 여행을 만들어
정산 엔진에 던지고 불변식이 깨지는지 본다. 실패하면 시드만 있으면
그대로 재현된다.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from .models import (
    CATEGORIES, POT_ID, SPLIT_EQUAL, SPLIT_EXACT, SPLIT_PERCENT, SPLIT_WEIGHT,
    TRANSFER_PLAIN, TRANSFER_POT_IN, Expense, Member, Payment, Transfer, Trip,
)

NAMES = ["민수", "지영", "현우", "서연", "준호", "다은", "태윤", "하린", "성민", "예린"]


def _random_partition(rng: random.Random, total: int, parts: int) -> list[int]:
    """total을 parts개 정수로 정확히 쪼갠다 (합계 보장)."""
    if parts <= 1:
        return [total]
    sign = -1 if total < 0 else 1
    magnitude = abs(total)
    cuts = sorted(rng.randint(0, magnitude) for _ in range(parts - 1))
    pieces = []
    previous = 0
    for cut in cuts:
        pieces.append(cut - previous)
        previous = cut
    pieces.append(magnitude - previous)
    return [sign * p for p in pieces]


def random_trip(seed: int) -> Trip:
    rng = random.Random(seed)
    member_count = rng.randint(2, 7)
    start = date(2025, 5, 1)
    length = rng.randint(1, 6)
    end = start + timedelta(days=length - 1)

    members = []
    for i in range(member_count):
        joined = left = None
        if rng.random() < 0.25 and length > 1:
            if rng.random() < 0.5:
                joined = start + timedelta(days=rng.randint(1, length - 1))
            else:
                left = start + timedelta(days=rng.randint(0, length - 2))
        members.append(Member(
            id=f"m{i}", name=NAMES[i % len(NAMES)] + (str(i // len(NAMES)) if i >= len(NAMES) else ""),
            weight=rng.choice([1, 1, 1, 0.5, 2, 1.5]),
            joined=joined, left=left,
        ))

    base = "KRW"
    rates: dict[str, float] = {}
    currencies = [base]
    if rng.random() < 0.4:
        rates["JPY"] = round(rng.uniform(8.5, 10.5), 3)
        currencies.append("JPY")
    if rng.random() < 0.3:
        rates["USD"] = round(rng.uniform(1200, 1450), 2)
        currencies.append("USD")

    use_pot = rng.random() < 0.35
    trip = Trip(
        id=f"fuzz{seed}", name=f"랜덤여행#{seed}", base_currency=base,
        start=start, end=end, members=members, rates=rates,
        rounding_unit=rng.choice([1, 1, 1, 10, 100, 1000]),
    )

    member_ids = [m.id for m in members]

    if use_pot:
        for mid in member_ids:
            if rng.random() < 0.85:
                trip.transfers.append(Transfer(
                    id=f"pot{mid}", from_id=mid, to_id=POT_ID,
                    amount=rng.randrange(10000, 200001, 10000), currency=base,
                    day=start, kind=TRANSFER_POT_IN,
                ))

    for i in range(rng.randint(0, 25)):
        currency = rng.choice(currencies)
        day = start + timedelta(days=rng.randint(0, length - 1))
        refund = rng.random() < 0.08
        if currency == "KRW":
            amount = rng.randrange(1000, 300001, 10)
        elif currency == "JPY":
            amount = rng.randrange(100, 40001, 10)
        else:
            amount = rng.randrange(100, 50001)
        if refund:
            amount = -amount

        # 결제자: 여러 명이 카드를 나눠 긁는 경우 포함
        payer_pool = list(member_ids)
        if use_pot and rng.random() < 0.3:
            payers = [POT_ID]
        else:
            count = 1 if rng.random() < 0.8 else min(len(payer_pool), rng.randint(2, 3))
            payers = rng.sample(payer_pool, count)
        payments = [
            Payment(member_id=pid, amount=part)
            for pid, part in zip(payers, _random_partition(rng, amount, len(payers)))
        ]

        # 분담 대상: 비워두면 그날 참여 중인 전원이 자동으로 들어간다
        if rng.random() < 0.5:
            participants: list[str] = []
        else:
            participants = rng.sample(member_ids, rng.randint(1, len(member_ids)))

        effective = participants or [
            m.id for m in trip.active_members_on(day)
        ]
        method = rng.choice([SPLIT_EQUAL, SPLIT_EQUAL, SPLIT_WEIGHT, SPLIT_EXACT, SPLIT_PERCENT])
        split_values: dict[str, float] = {}
        adjustments: dict[str, int] = {}

        if method == SPLIT_WEIGHT:
            weights = {mid: rng.choice([0, 0.5, 1, 1, 2, 3]) for mid in effective}
            if sum(weights.values()) == 0:
                weights[effective[0]] = 1
            split_values = weights
        elif method == SPLIT_PERCENT:
            raw = _random_partition(rng, 100, len(effective))
            split_values = {mid: float(abs(v)) for mid, v in zip(effective, raw)}
            drift = 100 - sum(split_values.values())
            split_values[effective[0]] += drift
        elif method == SPLIT_EXACT:
            parts = _random_partition(rng, amount, len(effective))
            split_values = {mid: float(v) for mid, v in zip(effective, parts)}
        elif not refund and rng.random() < 0.25:
            # "누가 얼마 더 내기로 함"
            room = abs(amount) // 2
            if room > 0:
                picks = rng.sample(effective, min(len(effective), rng.randint(1, 2)))
                for mid in picks:
                    adjustments[mid] = rng.randint(0, max(1, room // len(picks)))

        trip.expenses.append(Expense(
            id=f"e{seed}_{i}", title=f"지출{i}", amount=amount, currency=currency,
            day=day, category=rng.choice(CATEGORIES), payments=payments,
            split_method=method, participants=participants,
            split_values=split_values, adjustments=adjustments,
            exclude_from_settlement=(POT_ID not in payers and rng.random() < 0.07),
        ))

    for i in range(rng.randint(0, 4)):
        if len(member_ids) < 2:
            break
        a, b = rng.sample(member_ids, 2)
        trip.transfers.append(Transfer(
            id=f"t{seed}_{i}", from_id=a, to_id=b,
            amount=rng.randrange(1000, 200001, 1000), currency=base,
            day=start + timedelta(days=rng.randint(0, length - 1)),
            kind=TRANSFER_PLAIN,
        ))

    return trip
