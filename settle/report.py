"""정산 결과를 사람이 읽을 수 있게 출력."""

from __future__ import annotations

from datetime import date as _date

from .engine import Settlement
from .invariants import Verification, cross_check_total, verify
from .models import POT_ID, Trip
from .money import format_money
from .textui import bar, heading, rule, table, truncate


def _money(amount: int, currency: str) -> str:
    return format_money(amount, currency)


def summary(settlement: Settlement, show_detail: bool = True) -> str:
    trip: Trip = settlement.trip
    cur = settlement.base_currency
    out: list[str] = []

    period = ""
    if trip.start and trip.end:
        period = f"  {trip.start} ~ {trip.end}"
    elif trip.start:
        period = f"  {trip.start} ~"
    out.append(heading(f"{trip.name} 정산{period}"))

    people = len(trip.members)
    out.append(f"  참가자 {people}명 · 기준통화 {cur}"
               + (f" · 송금 반올림 {trip.rounding_unit:,} 단위" if trip.rounding_unit > 1 else ""))
    out.append("")
    out.append(f"  총 지출      {_money(settlement.total, cur)}")
    if people:
        out.append(f"  1인 평균     {_money(settlement.total // people, cur)}")
    if settlement.personal_total:
        out.append(f"  개인 지출    {_money(settlement.personal_total, cur)}  (정산 제외)")
    if len(settlement.by_currency) > 1:
        parts = [f"{format_money(v, k)}" for k, v in sorted(settlement.by_currency.items())]
        out.append("  통화별 원금  " + " / ".join(parts))
        rates = " / ".join(f"1{k}={v:g}{cur}" for k, v in sorted(trip.rates.items()))
        if rates:
            out.append(f"  적용 환율    {rates}")
    out.append("")

    # --- 사람별 -----------------------------------------------------
    out.append(rule("사람별 결제 · 부담 · 잔액"))
    rows = []
    for member in trip.members:
        balance = settlement.balances.get(member.id)
        if balance is None:
            continue
        net = settlement.rounded_net.get(member.id, balance.net)
        state = "받을 돈" if net > 0 else ("낼 돈" if net < 0 else "정산 완료")
        rows.append([
            member.name,
            _money(balance.paid, cur),
            _money(balance.owed, cur),
            _money(abs(net), cur) if net else "-",
            state,
        ])
    out.append(table(
        ["이름", "결제액", "부담액", "잔액", ""],
        rows, ["left", "right", "right", "right", "left"],
    ))
    out.append("")
    out.append("  * 결제액 = 실제로 긁은 돈 / 부담액 = 실제로 써야 할 몫")

    # --- 공금 -------------------------------------------------------
    if settlement.pot is not None:
        pot = settlement.pot
        out.append("")
        out.append(rule("공금(회비)"))
        out.append(f"  걷은 회비    {_money(pot.contributed, cur)}")
        out.append(f"  공금 지출    {_money(pot.spent, cur)}")
        out.append(f"  남은 공금    {_money(pot.balance, cur)}")
        if pot.per_member:
            rows = [[trip.member_name(mid), _money(amount, cur)]
                    for mid, amount in sorted(pot.per_member.items(),
                                              key=lambda kv: -kv[1])]
            out.append("")
            out.append(table(["납부자", "납부액"], rows, ["left", "right"]))

    # --- 이미 오간 돈 -----------------------------------------------
    plain = [t for t in trip.transfers if t.to_id != POT_ID]
    if plain:
        out.append("")
        out.append(rule("이미 주고받은 돈"))
        rows = [[
            str(t.day or "-"),
            f"{trip.member_name(t.from_id)} → {trip.member_name(t.to_id)}",
            format_money(t.amount, t.currency),
            t.note,
        ] for t in plain]
        out.append(table(["날짜", "송금", "금액", "메모"], rows,
                         ["left", "left", "right", "left"]))

    if show_detail:
        for section in (_category_section(settlement), _day_section(settlement)):
            if section:
                out.append(section)

    out.append("")
    out.append(_plan_section(settlement))

    if settlement.warnings:
        out.append("")
        out.append(rule("참고"))
        for warning in settlement.warnings:
            out.append(f"  · {warning}")
    return "\n".join(out)


def _category_section(settlement: Settlement) -> str:
    if not settlement.by_category:
        return ""
    cur = settlement.base_currency
    total = settlement.total or 1
    out = ["", rule("카테고리별")]
    rows = []
    for category, amount in sorted(settlement.by_category.items(), key=lambda kv: -kv[1]):
        rows.append([
            category, _money(amount, cur), f"{amount * 100 / total:5.1f}%",
            bar(amount, total, 18),
        ])
    out.append(table(["카테고리", "금액", "비중", ""], rows,
                     ["left", "right", "right", "left"]))
    return "\n".join(out)


def _day_section(settlement: Settlement) -> str:
    if not settlement.by_day:
        return ""
    cur = settlement.base_currency
    peak = max(settlement.by_day.values()) or 1
    out = ["", rule("날짜별")]
    rows = [[day, _money(amount, cur), bar(amount, peak, 18)]
            for day, amount in sorted(settlement.by_day.items())]
    out.append(table(["날짜", "금액", ""], rows, ["left", "right", "left"]))
    return "\n".join(out)


def _plan_section(settlement: Settlement) -> str:
    trip = settlement.trip
    cur = settlement.base_currency
    out = [rule("최종 송금안")]
    if not settlement.plan:
        out.append("  주고받을 돈이 없습니다. 정산 완료!")
        return "\n".join(out)
    for i, transfer in enumerate(settlement.plan, 1):
        sender = trip.member_name(transfer.from_id)
        receiver = trip.member_name(transfer.to_id)
        out.append(f"  {i}. {sender} → {receiver}   {_money(transfer.amount, cur)}")
    out.append("")
    out.append(f"  송금 {len(settlement.plan)}회로 정산이 끝납니다.")
    return "\n".join(out)


def verification_report(settlement: Settlement, verification: Verification | None = None) -> str:
    verification = verification or verify(settlement)
    checks = list(verification.checks) + [cross_check_total(settlement)]
    out = [rule("검증 (폐루프)")]
    for check in checks:
        mark = "✔" if check.ok else "✘"
        line = f"  {mark} {check.code}  {check.title}"
        if check.detail:
            line += f"  — {check.detail}"
        out.append(line)
    ok = all(c.ok for c in checks)
    out.append("")
    out.append("  ✔ 모든 검증을 통과했습니다. 이 정산 결과는 신뢰할 수 있습니다."
               if ok else
               "  ✘ 검증에 실패했습니다. 위 항목을 확인하세요.")
    return "\n".join(out)


def share_text(settlement: Settlement) -> str:
    """메신저에 붙여넣기 좋은 짧은 요약."""
    trip = settlement.trip
    cur = settlement.base_currency
    lines = [f"[{trip.name}] 정산 결과",
             f"총 지출 {_money(settlement.total, cur)} / {len(trip.members)}명"]
    lines.append("")
    for member in trip.members:
        balance = settlement.balances.get(member.id)
        if not balance:
            continue
        net = settlement.rounded_net.get(member.id, balance.net)
        mark = "받을 돈" if net > 0 else ("낼 돈" if net < 0 else "정산 완료")
        lines.append(f"- {member.name}: 결제 {_money(balance.paid, cur)} / "
                     f"부담 {_money(balance.owed, cur)} → {mark} "
                     f"{_money(abs(net), cur) if net else ''}".rstrip())
    lines.append("")
    if settlement.plan:
        lines.append("송금")
        for transfer in settlement.plan:
            lines.append(f"- {trip.member_name(transfer.from_id)} → "
                         f"{trip.member_name(transfer.to_id)} "
                         f"{_money(transfer.amount, cur)}")
    else:
        lines.append("주고받을 돈 없음 (정산 완료)")
    return "\n".join(lines)


def expense_list(settlement: Settlement, limit: int | None = None) -> str:
    trip = settlement.trip
    rows = []
    expenses = sorted(trip.expenses,
                      key=lambda e: (e.day or trip.start or _date.min, e.id))
    if limit:
        expenses = expenses[-limit:]
    for expense in expenses:
        payers = ", ".join(trip.member_name(p.member_id) for p in expense.payments) or "-"
        flag = " [개인]" if expense.exclude_from_settlement else ""
        rows.append([
            expense.id[:8],
            str(expense.day or "-"),
            truncate(expense.title, 22) + flag,
            expense.category,
            format_money(expense.amount, expense.currency),
            truncate(payers, 16),
            expense.split_method,
        ])
    if not rows:
        return "  등록된 지출이 없습니다."
    return table(
        ["ID", "날짜", "내용", "카테고리", "금액", "결제자", "분할"],
        rows, ["left", "left", "left", "left", "right", "left", "left"],
    )
