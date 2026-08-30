"""폐루프 검증.

정산 결과가 "돈이 맞는지"를 프로그램 스스로 검사한다. 계산할 때마다 돌리고,
결과 화면에도 통과 여부를 표시한다. 하나라도 깨지면 그 정산 결과는 못 믿는다.
"""

from __future__ import annotations

from dataclasses import dataclass

from .engine import Settlement, apply_plan
from .models import POT_ID, Trip
from .split import to_base


@dataclass
class Check:
    code: str
    title: str
    ok: bool
    detail: str = ""


@dataclass
class Verification:
    checks: list[Check]

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.ok]


def verify(settlement: Settlement) -> Verification:
    trip: Trip = settlement.trip
    checks: list[Check] = []
    unit = max(1, int(trip.rounding_unit or 1))

    # I1: 지출별 분할 합계 == 환산 총액
    bad = [
        s for s in settlement.splits if sum(s.owed.values()) != s.base_total
    ]
    checks.append(Check(
        "I1", "지출별 분할 합계가 각 지출 금액과 일치",
        not bad,
        "" if not bad else f"{len(bad)}건 불일치: " + ", ".join(s.expense_id for s in bad[:5]),
    ))

    # I1b: 지출별 결제액 합계 == 환산 총액
    bad_paid = [
        s for s in settlement.splits
        if s.paid and sum(s.paid.values()) != s.base_total
    ]
    checks.append(Check(
        "I2", "지출별 결제액 합계가 각 지출 금액과 일치",
        not bad_paid,
        "" if not bad_paid else f"{len(bad_paid)}건 불일치",
    ))

    # I3: 전체 결제액 합 == 전체 부담액 합 == 정산 대상 총액
    total_paid = sum(b.paid for b in settlement.balances.values())
    total_owed = sum(b.owed for b in settlement.balances.values())
    ok = total_paid == total_owed == settlement.total
    checks.append(Check(
        "I3", "전체 결제액 = 전체 부담액 = 총 지출",
        ok,
        "" if ok else f"결제 {total_paid:,} / 부담 {total_owed:,} / 총액 {settlement.total:,}",
    ))

    # I4: 잔액 합계 == 0
    raw_sum = sum(b.net for b in settlement.balances.values())
    checks.append(Check(
        "I4", "모든 사람의 잔액 합계가 0",
        raw_sum == 0,
        "" if raw_sum == 0 else f"합계 {raw_sum:,}",
    ))

    # I5: 역검증 — 송금안을 실제로 적용하면 전원 잔액 0
    after = apply_plan(settlement.rounded_net, settlement.plan)
    residual = {k: v for k, v in after.items() if v != 0}
    checks.append(Check(
        "I5", "송금안을 적용하면 전원 잔액이 0 (역검증)",
        not residual,
        "" if not residual else ", ".join(
            f"{trip.member_name(k)} {v:+,}" for k, v in list(residual.items())[:5]
        ),
    ))

    # I6: 보내면서 동시에 받는 사람이 없음
    senders = {t.from_id for t in settlement.plan}
    receivers = {t.to_id for t in settlement.plan}
    both = senders & receivers
    checks.append(Check(
        "I6", "보내면서 동시에 받는 사람이 없음",
        not both,
        "" if not both else ", ".join(trip.member_name(m) for m in both),
    ))

    # I7: 송금액은 모두 양수, 횟수는 (잔액이 0이 아닌 인원 - 1) 이하
    nonzero = sum(1 for v in settlement.rounded_net.values() if v != 0)
    max_transfers = max(0, nonzero - 1)
    positive = all(t.amount > 0 for t in settlement.plan)
    count_ok = len(settlement.plan) <= max_transfers
    checks.append(Check(
        "I7", "송금액은 모두 양수이고 송금 횟수가 최소 범위 안",
        positive and count_ok,
        "" if positive and count_ok else f"{len(settlement.plan)}회 / 상한 {max_transfers}회",
    ))

    # I8: 반올림 단위를 설정했으면 모든 송금액이 그 배수
    if unit > 1:
        off = [t for t in settlement.plan if t.amount % unit != 0]
        checks.append(Check(
            "I8", f"모든 송금액이 {unit:,} 단위",
            not off,
            "" if not off else f"{len(off)}건이 단위에 맞지 않음",
        ))

    # I9: 공금 수지가 맞음 (걷은 돈 = 쓴 돈 + 남은 돈)
    if settlement.pot is not None:
        pot = settlement.pot
        pot_balance = settlement.balances.get(POT_ID)
        expected_net = pot.spent - pot.contributed
        actual = pot_balance.net if pot_balance else 0
        ok_pot = expected_net == actual
        checks.append(Check(
            "I9", "공금 수지 일치 (걷은 돈 = 쓴 돈 + 남은 돈)",
            ok_pot,
            "" if ok_pot else f"기대 {expected_net:,} / 실제 {actual:,}",
        ))

    # I10: 개인 지출은 정산 총액에 섞이지 않음
    personal_paid = sum(b.personal for b in settlement.balances.values())
    ok_personal = personal_paid == settlement.personal_total
    checks.append(Check(
        "I10", "정산 제외 개인 지출이 정산 총액에 섞이지 않음",
        ok_personal,
        "" if ok_personal else f"{personal_paid:,} != {settlement.personal_total:,}",
    ))

    return Verification(checks=checks)


def cross_check_total(settlement: Settlement) -> Check:
    """지출 원장을 처음부터 다시 더해 총액을 독립적으로 재계산한다(이중 기장)."""
    trip = settlement.trip
    recomputed = 0
    for expense in trip.expenses:
        if expense.exclude_from_settlement:
            continue
        recomputed += to_base(trip, expense.amount, expense.currency, expense.rate)
    ok = recomputed == settlement.total
    return Check(
        "X1", "총액 독립 재계산 일치",
        ok,
        "" if ok else f"재계산 {recomputed:,} != {settlement.total:,}",
    )
