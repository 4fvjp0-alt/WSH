"""잔액 집계와 최소 송금 계산."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Optional

from .models import POT_ID, TRANSFER_POT_IN, Trip
from .money import round_preserving_sum
from .split import SettleError, SplitResult, split_expense, to_base

# 인원이 이 수 이하면 최적 송금안(부분집합 DP)을 구한다. 넘으면 그리디.
EXACT_OPTIMIZE_LIMIT = 12


@dataclass
class MemberBalance:
    member_id: str
    paid: int = 0            # 실제로 결제한 금액
    owed: int = 0            # 실제로 부담해야 할 금액
    sent: int = 0            # 이미 보낸 돈 (중간 송금 + 회비 입금)
    received: int = 0        # 이미 받은 돈
    personal: int = 0        # 정산에서 제외한 개인 지출

    @property
    def net(self) -> int:
        """양수면 받아야 할 돈, 음수면 내야 할 돈."""
        return self.paid - self.owed + self.sent - self.received


@dataclass
class PlannedTransfer:
    from_id: str
    to_id: str
    amount: int


@dataclass
class PotInfo:
    contributed: int = 0     # 걷은 회비 총액
    spent: int = 0           # 공금에서 나간 지출
    per_member: dict[str, int] = field(default_factory=dict)

    @property
    def balance(self) -> int:
        return self.contributed - self.spent


@dataclass
class Settlement:
    trip: Trip
    base_currency: str
    total: int = 0                                   # 정산 대상 지출 총액
    personal_total: int = 0                          # 정산 제외 개인 지출 총액
    balances: dict[str, MemberBalance] = field(default_factory=dict)
    rounded_net: dict[str, int] = field(default_factory=dict)
    plan: list[PlannedTransfer] = field(default_factory=list)
    by_category: dict[str, int] = field(default_factory=dict)
    by_day: dict[str, int] = field(default_factory=dict)
    by_currency: dict[str, int] = field(default_factory=dict)
    splits: list[SplitResult] = field(default_factory=list)
    pot: Optional[PotInfo] = None
    warnings: list[str] = field(default_factory=list)

    def entities(self) -> list[str]:
        return list(self.balances.keys())

    def name(self, entity_id: str) -> str:
        return self.trip.member_name(entity_id)

    @property
    def per_head_average(self) -> int:
        people = [m for m in self.trip.members]
        return self.total // len(people) if people else 0


def _greedy_transfers(nets: list[tuple[str, int]]) -> list[PlannedTransfer]:
    """채권자·채무자를 큰 쪽부터 맞물려 송금 횟수를 줄인다."""
    creditors = sorted([list(x) for x in nets if x[1] > 0], key=lambda x: -x[1])
    debtors = sorted([list(x) for x in nets if x[1] < 0], key=lambda x: x[1])
    plan: list[PlannedTransfer] = []
    i = j = 0
    while i < len(creditors) and j < len(debtors):
        credit = creditors[i]
        debt = debtors[j]
        amount = min(credit[1], -debt[1])
        if amount > 0:
            plan.append(PlannedTransfer(from_id=debt[0], to_id=credit[0], amount=amount))
        credit[1] -= amount
        debt[1] += amount
        if credit[1] == 0:
            i += 1
        if debt[1] == 0:
            j += 1
    return plan


def _optimal_groups(nets: list[tuple[str, int]]) -> list[list[tuple[str, int]]]:
    """합이 0인 부분집합으로 최대한 잘게 쪼갠다.

    잔액을 g개의 '합이 0인 그룹'으로 나눌 수 있으면 송금 횟수는 n-g 로 줄어든다.
    그룹 개수를 최대화하는 것이 곧 송금 횟수 최소화다.
    """
    n = len(nets)
    full = (1 << n) - 1
    sums = [0] * (1 << n)
    for mask in range(1, 1 << n):
        low = (mask & -mask).bit_length() - 1
        sums[mask] = sums[mask & (mask - 1)] + nets[low][1]

    best_count = [-1] * (1 << n)
    best_pick = [0] * (1 << n)
    best_count[0] = 0
    for mask in range(1, 1 << n):
        if sums[mask] != 0:
            continue
        low_bit = mask & -mask
        sub = mask
        while sub:
            if (sub & low_bit) and sums[sub] == 0 and best_count[mask ^ sub] >= 0:
                candidate = best_count[mask ^ sub] + 1
                if candidate > best_count[mask]:
                    best_count[mask] = candidate
                    best_pick[mask] = sub
            sub = (sub - 1) & mask

    groups: list[list[tuple[str, int]]] = []
    mask = full
    while mask:
        pick = best_pick[mask]
        if not pick:  # pragma: no cover - 전체 합이 0이면 항상 해가 있다
            pick = mask
        groups.append([nets[i] for i in range(n) if pick >> i & 1])
        mask ^= pick
    return groups


def minimal_transfers(
    nets: dict[str, int], optimize_limit: int = EXACT_OPTIMIZE_LIMIT
) -> list[PlannedTransfer]:
    """잔액을 0으로 만드는 송금 목록. 횟수를 최소화한다."""
    items = [(k, v) for k, v in nets.items() if v != 0]
    if not items:
        return []
    if sum(v for _, v in items) != 0:
        raise AssertionError("잔액 합계가 0이 아닙니다")
    if len(items) <= optimize_limit:
        plan: list[PlannedTransfer] = []
        for group in _optimal_groups(items):
            plan.extend(_greedy_transfers(group))
        return plan
    return _greedy_transfers(items)


def compute(trip: Trip, optimize_limit: int = EXACT_OPTIMIZE_LIMIT) -> Settlement:
    """여행 하나를 정산한다."""
    result = Settlement(trip=trip, base_currency=trip.base_currency)

    def balance(entity_id: str) -> MemberBalance:
        if entity_id not in result.balances:
            result.balances[entity_id] = MemberBalance(member_id=entity_id)
        return result.balances[entity_id]

    for member in trip.members:
        balance(member.id)

    uses_pot = trip.uses_pot()
    if uses_pot:
        balance(POT_ID)

    for expense in trip.expenses:
        split = split_expense(trip, expense)
        result.splits.append(split)
        if expense.exclude_from_settlement:
            result.personal_total += split.base_total
            for mid, amount in split.paid.items():
                balance(mid).personal += amount
            continue
        result.total += split.base_total
        for mid, amount in split.paid.items():
            balance(mid).paid += amount
        for mid, amount in split.owed.items():
            balance(mid).owed += amount
        result.by_category[expense.category] = (
            result.by_category.get(expense.category, 0) + split.base_total
        )
        day_key = expense.day.isoformat() if expense.day else "날짜 없음"
        result.by_day[day_key] = result.by_day.get(day_key, 0) + split.base_total
        cur = expense.currency.upper()
        result.by_currency[cur] = result.by_currency.get(cur, 0) + expense.amount

    pot = PotInfo() if uses_pot else None
    for transfer in trip.transfers:
        amount = to_base(trip, transfer.amount, transfer.currency, transfer.rate)
        known = {m.id for m in trip.members} | {POT_ID}
        if transfer.from_id not in known or transfer.to_id not in known:
            raise SettleError(f"송금 기록에 알 수 없는 대상이 있습니다: {transfer.id}")
        if transfer.from_id == transfer.to_id:
            raise SettleError(f"보내는 사람과 받는 사람이 같습니다: {transfer.id}")
        balance(transfer.from_id).sent += amount
        balance(transfer.to_id).received += amount
        if pot is not None and transfer.kind == TRANSFER_POT_IN:
            pot.contributed += amount
            pot.per_member[transfer.from_id] = pot.per_member.get(transfer.from_id, 0) + amount

    if pot is not None:
        pot.spent = result.balances[POT_ID].paid + result.balances[POT_ID].personal
        result.pot = pot
        if pot.balance < 0:
            result.warnings.append(
                f"공금이 걷은 금액보다 {-pot.balance:,} 더 쓰였습니다. "
                "최종 송금안에 공금이 받아야 할 돈으로 반영됩니다."
            )

    nets = {eid: bal.net for eid, bal in result.balances.items()}
    if sum(nets.values()) != 0:
        raise AssertionError(f"잔액 합계가 0이 아닙니다: {sum(nets.values())}")

    unit = max(1, int(trip.rounding_unit or 1))
    if unit > 1:
        keys = list(nets.keys())
        rounded = round_preserving_sum([nets[k] for k in keys], unit)
        nets = dict(zip(keys, rounded))
        for eid, value in nets.items():
            drift = value - result.balances[eid].net
            if drift:
                result.warnings.append(
                    f"{trip.member_name(eid)}: {unit:,} 단위 반올림으로 {drift:+,} 조정"
                )
    result.rounded_net = nets
    result.plan = minimal_transfers(nets, optimize_limit)
    return result


def apply_plan(nets: dict[str, int], plan: Iterable[PlannedTransfer]) -> dict[str, int]:
    """송금안을 실제로 적용했을 때의 잔액. 역검증(불변식 I4)에 쓴다."""
    after = dict(nets)
    for t in plan:
        after[t.from_id] = after.get(t.from_id, 0) + t.amount
        after[t.to_id] = after.get(t.to_id, 0) - t.amount
    return after
