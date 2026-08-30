"""분할 규칙 엔진.

지출 한 건을 "누가 얼마를 부담하는가"로 변환한다. 결과 금액의 합계는
기준통화로 환산된 지출 총액과 **정확히** 일치한다(불변식 I1).
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from typing import Optional

from .models import (
    POT_ID, SPLIT_EQUAL, SPLIT_EXACT, SPLIT_METHODS, SPLIT_PERCENT,
    SPLIT_WEIGHT, Expense, Trip,
)
from .money import allocate, convert


class SettleError(Exception):
    """정산을 계속할 수 없는 데이터 오류."""


@dataclass
class SplitResult:
    expense_id: str
    base_total: int                       # 기준통화 환산 총액
    participants: list[str]
    owed: dict[str, int] = field(default_factory=dict)   # 멤버 -> 부담액(기준통화)
    paid: dict[str, int] = field(default_factory=dict)   # 멤버 -> 결제액(기준통화)


def _seed_for(expense_id: str) -> int:
    """지출마다 나머지 1원의 귀속 순서를 다르게 회전시키기 위한 시드."""
    return zlib.crc32(expense_id.encode("utf-8"))


def rate_for(trip: Trip, expense_currency: str, override: Optional[float] = None) -> Optional[float]:
    if expense_currency.upper() == trip.base_currency.upper():
        return None
    if override is not None:
        return override
    rate = trip.rates.get(expense_currency.upper())
    if rate is None:
        raise SettleError(
            f"{expense_currency} → {trip.base_currency} 환율이 등록되지 않았습니다. "
            f"`rate set {expense_currency} <환율>` 로 등록하세요."
        )
    return rate


def to_base(trip: Trip, amount: int, currency: str, override: Optional[float] = None) -> int:
    rate = rate_for(trip, currency, override)
    return convert(amount, currency, trip.base_currency, rate)


def resolve_participants(trip: Trip, expense: Expense) -> list[str]:
    """분담 대상 확정. 비어 있으면 그날 여행에 참여 중인 멤버 전원."""
    known = {m.id for m in trip.members}
    if expense.participants:
        ids = [p for p in expense.participants]
    else:
        ids = [m.id for m in trip.active_members_on(expense.day)]
    # 조정액이나 분할값이 지정된 사람은 참여자로 간주한다.
    # (분담 대상을 따로 안 적고 '지영=2' 처럼 값만 준 경우를 살리기 위함)
    for mid in list(expense.adjustments) + list(expense.split_values):
        if mid not in ids:
            ids.append(mid)
    result: list[str] = []
    for mid in ids:
        if mid == POT_ID:
            raise SettleError(f"[{expense.title}] 공금은 분담 대상이 될 수 없습니다")
        if mid not in known:
            raise SettleError(f"[{expense.title}] 알 수 없는 멤버가 분담 대상에 있습니다: {mid}")
        if mid not in result:
            result.append(mid)
    if not result:
        raise SettleError(f"[{expense.title}] 분담할 사람이 없습니다")
    return result


def _weights_for(trip: Trip, expense: Expense, participants: list[str]) -> list:
    method = expense.split_method
    if method not in SPLIT_METHODS:
        raise SettleError(f"[{expense.title}] 알 수 없는 분할 방식: {method}")

    if method == SPLIT_EQUAL:
        return [1] * len(participants)

    if method == SPLIT_WEIGHT:
        weights = []
        for mid in participants:
            member = trip.member(mid)
            default = member.weight if member else 1.0
            weights.append(expense.split_values.get(mid, default))
        if sum(weights) <= 0:
            raise SettleError(f"[{expense.title}] 가중치 합이 0입니다")
        return weights

    if method == SPLIT_PERCENT:
        weights = [expense.split_values.get(mid, 0.0) for mid in participants]
        total = sum(weights)
        if abs(total - 100.0) > 1e-6:
            raise SettleError(
                f"[{expense.title}] 비율 합계가 {total:g}%%입니다. 100%%가 되어야 합니다."
            )
        return weights

    # SPLIT_EXACT: 지정 금액을 그대로 비중으로 써서 기준통화로 정확히 환산한다.
    if expense.adjustments:
        raise SettleError(
            f"[{expense.title}] 금액 직접 지정(exact) 방식에는 별도 조정액을 함께 쓸 수 없습니다"
        )
    values = [expense.split_values.get(mid, 0.0) for mid in participants]
    total = round(sum(values))
    if total != expense.amount:
        raise SettleError(
            f"[{expense.title}] 지정 금액 합계({total:,})가 지출 금액({expense.amount:,})과 다릅니다"
        )
    if any(v < 0 for v in values) and expense.amount >= 0:
        raise SettleError(f"[{expense.title}] 지정 금액에 음수가 있습니다")
    return values


def split_expense(trip: Trip, expense: Expense) -> SplitResult:
    """지출 한 건의 부담액/결제액을 기준통화로 계산한다."""
    base_total = to_base(trip, expense.amount, expense.currency, expense.rate)
    participants = resolve_participants(trip, expense)
    seed = _seed_for(expense.id)

    # --- 결제액: 결제자별 금액 비율대로 기준통화 총액을 정확히 배분 ----
    if not expense.payments:
        if expense.amount != 0:
            raise SettleError(f"[{expense.title}] 결제한 사람이 지정되지 않았습니다")
        paid: dict[str, int] = {}
    else:
        paid_sum = expense.total_paid
        if paid_sum != expense.amount:
            raise SettleError(
                f"[{expense.title}] 결제액 합계({paid_sum:,})가 "
                f"지출 금액({expense.amount:,})과 다릅니다"
            )
        known = {m.id for m in trip.members} | {POT_ID}
        for p in expense.payments:
            if p.member_id not in known:
                raise SettleError(f"[{expense.title}] 알 수 없는 결제자: {p.member_id}")
            if p.member_id == POT_ID and expense.exclude_from_settlement:
                raise SettleError(
                    f"[{expense.title}] 공금이 결제한 지출은 정산에서 제외할 수 없습니다. "
                    "공금은 참가자 모두의 돈이라 개인 지출로 뺄 수 없습니다."
                )
        if len(expense.payments) == 1:
            shares = [base_total]
        else:
            # 환불 건은 결제액도 음수다. 비중은 절댓값, 부호는 총액이 결정한다.
            magnitudes = [abs(p.amount) for p in expense.payments]
            if sum(magnitudes) == 0:
                magnitudes = [1] * len(expense.payments)
            shares = allocate(base_total, magnitudes, seed)
        paid = {}
        for p, share in zip(expense.payments, shares):
            paid[p.member_id] = paid.get(p.member_id, 0) + share

    # --- 조정액("누가 얼마 더 내기로 함") -----------------------------
    adjustments_base: dict[str, int] = {}
    if expense.adjustments:
        if base_total < 0:
            raise SettleError(f"[{expense.title}] 환불 건에는 조정액을 쓸 수 없습니다")
        for mid, amount in expense.adjustments.items():
            adjustments_base[mid] = to_base(trip, amount, expense.currency, expense.rate)
    adjust_sum = sum(adjustments_base.values())
    remainder = base_total - adjust_sum
    if base_total >= 0 and remainder < 0:
        raise SettleError(
            f"[{expense.title}] 조정액 합계가 지출 금액을 넘습니다 "
            f"(조정 {adjust_sum:,} > 총액 {base_total:,})"
        )

    # --- 나머지를 규칙대로 분할 --------------------------------------
    weights = _weights_for(trip, expense, participants)
    if expense.split_method == SPLIT_EXACT:
        # 환불(음수) 건에서는 지정 금액도 음수다. 비중은 절댓값으로 쓰고
        # 부호는 총액이 결정한다.
        magnitudes = [abs(w) for w in weights]
        if sum(magnitudes) == 0:
            magnitudes = [1] * len(participants)
        shares = allocate(base_total, magnitudes, seed) if base_total else [0] * len(participants)
    else:
        shares = allocate(remainder, weights, seed) if remainder else [0] * len(participants)

    owed: dict[str, int] = {}
    for mid, share in zip(participants, shares):
        owed[mid] = owed.get(mid, 0) + share
    for mid, amount in adjustments_base.items():
        owed[mid] = owed.get(mid, 0) + amount

    # 불변식 I1: 분할 합계 == 환산 총액
    if sum(owed.values()) != base_total:
        raise AssertionError(
            f"[{expense.title}] 분할 합계가 총액과 다릅니다 "
            f"({sum(owed.values())} != {base_total})"
        )

    return SplitResult(
        expense_id=expense.id, base_total=base_total,
        participants=participants, owed=owed, paid=paid,
    )
