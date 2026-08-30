"""명령행 인터페이스."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from . import __version__, category as category_mod, ocr_claude, store
from .cliutil import (
    InputError, ask, confirm, parse_amounts, parse_day, parse_members,
    parse_payers, parse_values, resolve_entity,
)
from .engine import compute
from .fuzz import random_trip
from .invariants import cross_check_total, verify
from .models import (
    CATEGORIES, POT_ID, SPLIT_EQUAL, SPLIT_EXACT, SPLIT_METHODS, SPLIT_PERCENT,
    SPLIT_WEIGHT, TRANSFER_PLAIN, TRANSFER_POT_IN, Book, Expense, Member,
    Payment, Transfer, Trip, new_id,
)
from .money import format_money, minor_digits, to_minor
from .parse_text import ParsedTx, parse_text
from .report import (
    expense_list, share_text, summary, verification_report,
)
from .split import SettleError
from .textui import heading, rule, table


class CliError(Exception):
    pass


# ---------------------------------------------------------------- 공통

def current_trip(book: Book) -> Trip:
    trip = book.current()
    if trip is None:
        raise CliError("등록된 여행이 없습니다. `trip new <이름>` 으로 먼저 만드세요.")
    return trip


def pick_trip(book: Book, query: Optional[str]) -> Trip:
    if not query:
        return current_trip(book)
    found = book.find_trips(query)
    if not found:
        raise CliError(f"'{query}' 에 해당하는 여행이 없습니다")
    if len(found) > 1:
        raise CliError("여러 여행과 일치합니다: " + ", ".join(t.name for t in found))
    return found[0]


def trip_year(trip: Trip) -> int:
    """날짜에 연도가 빠졌을 때 쓸 기본 연도. 오늘이 아니라 여행 연도를 쓴다.

    작년 여행을 나중에 정산하는 일이 흔한데, 오늘 연도를 쓰면 '09-05' 가
    엉뚱한 해로 들어가 참여 기간 판정까지 어긋난다.
    """
    return (trip.start or trip.end or date.today()).year


def _amount_hint(currency: str) -> str:
    return "정수" if minor_digits(currency) == 0 else f"소수점 {minor_digits(currency)}자리까지"


# ---------------------------------------------------------------- trip

def cmd_trip_new(book: Book, args) -> str:
    trip = Trip(
        id=new_id("trip_"), name=args.name,
        base_currency=(args.currency or "KRW").upper(),
        start=parse_day(args.start), end=parse_day(args.end),
        rounding_unit=max(1, args.rounding or 1),
    )
    book.trips.append(trip)
    book.current_trip_id = trip.id
    return f"여행 '{trip.name}' 을 만들었습니다. (현재 여행으로 선택됨)"


def cmd_trip_list(book: Book, args) -> str:
    if not book.trips:
        return "등록된 여행이 없습니다."
    current = book.current()
    rows = []
    for trip in book.trips:
        period = f"{trip.start or '-'} ~ {trip.end or '-'}"
        rows.append([
            "▶" if current and trip.id == current.id else " ",
            trip.name, period, f"{len(trip.members)}명",
            f"{len(trip.expenses)}건", trip.base_currency,
        ])
    return table(["", "이름", "기간", "인원", "지출", "통화"], rows)


def cmd_trip_use(book: Book, args) -> str:
    trip = pick_trip(book, args.name)
    book.current_trip_id = trip.id
    return f"현재 여행: {trip.name}"


def cmd_trip_set(book: Book, args) -> str:
    trip = current_trip(book)
    changed = []
    if args.name:
        trip.name = args.name
        changed.append("이름")
    if args.start:
        trip.start = parse_day(args.start)
        changed.append("시작일")
    if args.end:
        trip.end = parse_day(args.end)
        changed.append("종료일")
    if args.currency:
        trip.base_currency = args.currency.upper()
        changed.append("기준통화")
    if args.rounding is not None:
        trip.rounding_unit = max(1, args.rounding)
        changed.append("반올림 단위")
    if not changed:
        return "변경할 항목이 없습니다."
    return f"{trip.name}: {', '.join(changed)} 를 수정했습니다."


def cmd_trip_delete(book: Book, args) -> str:
    trip = pick_trip(book, args.name)
    if not args.yes and not confirm(f"'{trip.name}' 을(를) 삭제할까요? 되돌릴 수 없습니다", False):
        return "취소했습니다."
    book.trips = [t for t in book.trips if t.id != trip.id]
    if book.current_trip_id == trip.id:
        book.current_trip_id = book.trips[-1].id if book.trips else None
    return f"'{trip.name}' 을 삭제했습니다."


def cmd_trip_show(book: Book, args) -> str:
    trip = current_trip(book)
    out = [heading(trip.name)]
    out.append(f"  기간        {trip.start or '-'} ~ {trip.end or '-'}")
    out.append(f"  기준통화    {trip.base_currency}")
    out.append(f"  반올림      {trip.rounding_unit:,} 단위")
    if trip.rates:
        out.append("  환율        " + ", ".join(
            f"1{k}={v:g}{trip.base_currency}" for k, v in sorted(trip.rates.items())))
    out.append("")
    out.append(rule("참가자"))
    if trip.members:
        rows = [[
            m.name, f"{m.weight:g}인분",
            f"{m.joined or '처음'} ~ {m.left or '끝'}", m.note,
        ] for m in trip.members]
        out.append(table(["이름", "기본 인분", "참여 기간", "메모"], rows))
    else:
        out.append("  아직 없습니다. `member add <이름> ...`")
    out.append("")
    out.append(rule(f"지출 {len(trip.expenses)}건"))
    out.append(expense_list(compute(trip), limit=args.limit))
    return "\n".join(out)


# -------------------------------------------------------------- member

def cmd_member_add(book: Book, args) -> str:
    trip = current_trip(book)
    year = trip_year(trip)
    added = []
    for name in args.names:
        name = name.strip()
        if not name:
            continue
        if any(m.name == name for m in trip.members):
            raise CliError(f"'{name}' 은(는) 이미 있습니다")
        trip.members.append(Member(
            id=new_id("m_"), name=name, weight=args.weight,
            joined=parse_day(args.joined, year), left=parse_day(args.left, year),
            note=args.note or "",
        ))
        added.append(name)
    if not added:
        raise CliError("추가할 이름이 없습니다")
    return f"참가자 추가: {', '.join(added)} (총 {len(trip.members)}명)"


def cmd_member_list(book: Book, args) -> str:
    trip = current_trip(book)
    if not trip.members:
        return "참가자가 없습니다."
    rows = [[m.name, f"{m.weight:g}", f"{m.joined or '처음'} ~ {m.left or '끝'}", m.note]
            for m in trip.members]
    return table(["이름", "기본 인분", "참여 기간", "메모"], rows)


def cmd_member_set(book: Book, args) -> str:
    trip = current_trip(book)
    member = trip.resolve_member(args.name)
    if args.rename:
        member.name = args.rename
    if args.weight is not None:
        member.weight = args.weight
    year = trip_year(trip)
    if args.joined:
        member.joined = parse_day(args.joined, year)
    if args.left:
        member.left = parse_day(args.left, year)
    if args.note is not None:
        member.note = args.note
    return f"{member.name} 정보를 수정했습니다."


def cmd_member_remove(book: Book, args) -> str:
    trip = current_trip(book)
    member = trip.resolve_member(args.name)
    used = [e for e in trip.expenses
            if any(p.member_id == member.id for p in e.payments)
            or member.id in e.participants or member.id in e.adjustments]
    used += [t for t in trip.transfers if member.id in (t.from_id, t.to_id)]
    if used:
        raise CliError(
            f"{member.name} 은(는) 지출/송금 {len(used)}건에 걸려 있어 삭제할 수 없습니다. "
            "해당 기록을 먼저 정리하세요."
        )
    trip.members = [m for m in trip.members if m.id != member.id]
    return f"{member.name} 을(를) 참가자에서 뺐습니다."


# ---------------------------------------------------------------- rate

def cmd_rate_set(book: Book, args) -> str:
    trip = current_trip(book)
    code = args.currency.upper()
    if code == trip.base_currency:
        raise CliError("기준통화에는 환율이 필요 없습니다")
    trip.rates[code] = float(args.rate)
    return f"환율 등록: 1 {code} = {args.rate:g} {trip.base_currency}"


def cmd_rate_list(book: Book, args) -> str:
    trip = current_trip(book)
    if not trip.rates:
        return "등록된 환율이 없습니다."
    rows = [[k, f"1 {k} = {v:g} {trip.base_currency}"] for k, v in sorted(trip.rates.items())]
    return table(["통화", "환율"], rows)


# ------------------------------------------------------------- expense

def _build_expense(trip: Trip, book: Book, args) -> Expense:
    currency = (args.currency or trip.base_currency).upper()

    title = args.title or ask("내용 (예: 흑돼지 저녁)", required=True)
    if not title:
        raise CliError("내용을 입력하세요")

    raw_amount = args.amount or ask(f"금액 ({currency}, {_amount_hint(currency)})", required=True)
    if not raw_amount:
        raise CliError("금액을 입력하세요")
    amount = to_minor(raw_amount, currency)
    if amount == 0:
        raise CliError("금액이 0입니다")

    year = trip_year(trip)
    day = parse_day(args.date, year) if args.date else parse_day(
        ask("날짜 (예: 08-29, 오늘)", (trip.start or date.today()).isoformat()), year)

    payer_spec = args.payer or ask(
        "결제한 사람 (여러 명이면 '민수:60000,지영:30000', 공금이면 '공금')", required=True)
    payments = parse_payers(trip, payer_spec, amount, currency)

    suggested = category_mod.classify(title, book.category_hints)
    cat = args.category or ask(f"카테고리 ({'/'.join(CATEGORIES)})", suggested)
    if cat not in CATEGORIES:
        raise CliError(f"알 수 없는 카테고리: {cat}\n사용 가능: {', '.join(CATEGORIES)}")
    if cat != suggested:
        category_mod.learn(book.category_hints, title, cat)

    method = args.split or SPLIT_EQUAL
    if method not in SPLIT_METHODS:
        raise CliError(f"분할 방식은 {', '.join(SPLIT_METHODS)} 중 하나입니다")

    participants = parse_members(trip, args.who)
    split_values: dict[str, float] = {}
    if method in (SPLIT_WEIGHT, SPLIT_PERCENT):
        split_values = parse_values(trip, args.values)
    elif method == SPLIT_EXACT:
        exact = parse_amounts(trip, args.values, currency)
        if not exact:
            raise CliError("exact 분할에는 --values '민수=50000,지영=30000' 이 필요합니다")
        split_values = {k: float(v) for k, v in exact.items()}
        if not participants:
            participants = list(exact.keys())

    adjustments = parse_amounts(trip, args.extra, currency)

    expense = Expense(
        id=new_id("e_"), title=title, amount=amount, currency=currency, day=day,
        category=cat, payments=payments, split_method=method,
        participants=participants, split_values=split_values,
        adjustments=adjustments, rate=args.rate,
        exclude_from_settlement=bool(args.personal), note=args.note or "",
        source=args.source, image_path=args.image or "",
    )
    return expense


def cmd_expense_add(book: Book, args) -> str:
    trip = current_trip(book)
    if not trip.members:
        raise CliError("참가자를 먼저 추가하세요: `member add 민수 지영`")
    expense = _build_expense(trip, book, args)
    trip.expenses.append(expense)
    settlement = compute(trip)  # 즉시 검증: 잘못된 입력이면 여기서 걸린다
    split = next(s for s in settlement.splits if s.expense_id == expense.id)
    lines = [f"등록: [{expense.id[:8]}] {expense.title} "
             f"{format_money(expense.amount, expense.currency)} ({expense.category})"]
    lines.append("  부담: " + ", ".join(
        f"{trip.member_name(mid)} {format_money(amount, trip.base_currency)}"
        for mid, amount in split.owed.items()))
    return "\n".join(lines)


def cmd_expense_list(book: Book, args) -> str:
    trip = current_trip(book)
    return expense_list(compute(trip), limit=args.limit)


def cmd_expense_show(book: Book, args) -> str:
    trip = current_trip(book)
    expense = _find_expense(trip, args.id)
    settlement = compute(trip)
    split = next(s for s in settlement.splits if s.expense_id == expense.id)
    out = [rule(f"{expense.title}  [{expense.id[:8]}]")]
    out.append(f"  날짜        {expense.day or '-'}")
    out.append(f"  금액        {format_money(expense.amount, expense.currency)}"
               + ("" if expense.currency == trip.base_currency
                  else f"  →  {format_money(split.base_total, trip.base_currency)}"))
    out.append(f"  카테고리    {expense.category}")
    out.append("  결제        " + ", ".join(
        f"{trip.member_name(p.member_id)} {format_money(p.amount, expense.currency)}"
        for p in expense.payments))
    out.append(f"  분할 방식   {expense.split_method}")
    if expense.adjustments:
        out.append("  추가 부담   " + ", ".join(
            f"{trip.member_name(mid)} +{format_money(amount, expense.currency)}"
            for mid, amount in expense.adjustments.items()))
    if expense.exclude_from_settlement:
        out.append("  정산 제외   예 (개인 지출)")
    if expense.note:
        out.append(f"  메모        {expense.note}")
    if expense.source != "manual":
        out.append(f"  입력 경로   {expense.source}"
                   + (f"  ({expense.image_path})" if expense.image_path else ""))
    out.append("")
    rows = [[trip.member_name(mid), format_money(amount, trip.base_currency)]
            for mid, amount in split.owed.items()]
    out.append(table(["부담자", "부담액"], rows, ["left", "right"]))
    return "\n".join(out)


def _find_expense(trip: Trip, key: str) -> Expense:
    matches = [e for e in trip.expenses if e.id == key or e.id.startswith(key)]
    if not matches:
        matches = [e for e in trip.expenses if key in e.title]
    if not matches:
        raise CliError(f"'{key}' 에 해당하는 지출이 없습니다")
    if len(matches) > 1:
        raise CliError("여러 지출과 일치합니다: " + ", ".join(
            f"{e.id[:8]}({e.title})" for e in matches[:6]))
    return matches[0]


def cmd_expense_edit(book: Book, args) -> str:
    trip = current_trip(book)
    expense = _find_expense(trip, args.id)
    currency = (args.currency or expense.currency).upper()
    if args.title:
        expense.title = args.title
    if args.amount:
        expense.amount = to_minor(args.amount, currency)
    if args.currency:
        expense.currency = currency
    if args.date:
        expense.day = parse_day(args.date, trip_year(trip))
    if args.category:
        if args.category not in CATEGORIES:
            raise CliError(f"알 수 없는 카테고리: {args.category}")
        expense.category = args.category
        category_mod.learn(book.category_hints, expense.title, args.category)
    if args.payer:
        expense.payments = parse_payers(trip, args.payer, expense.amount, expense.currency)
    if args.split:
        expense.split_method = args.split
    if args.who is not None:
        expense.participants = parse_members(trip, args.who)
    if args.values is not None:
        if expense.split_method == SPLIT_EXACT:
            expense.split_values = {
                k: float(v) for k, v in parse_amounts(trip, args.values, expense.currency).items()
            }
        else:
            expense.split_values = parse_values(trip, args.values)
    if args.extra is not None:
        expense.adjustments = parse_amounts(trip, args.extra, expense.currency)
    if args.note is not None:
        expense.note = args.note
    if args.personal is not None:
        expense.exclude_from_settlement = args.personal
    compute(trip)
    return f"[{expense.id[:8]}] {expense.title} 를 수정했습니다."


def cmd_expense_remove(book: Book, args) -> str:
    trip = current_trip(book)
    expense = _find_expense(trip, args.id)
    if not args.yes and not confirm(f"'{expense.title}' 삭제할까요?", False):
        return "취소했습니다."
    trip.expenses = [e for e in trip.expenses if e.id != expense.id]
    return f"'{expense.title}' 을 삭제했습니다."


# ------------------------------------------------------- pot / transfer

def cmd_pot_in(book: Book, args) -> str:
    trip = current_trip(book)
    member = trip.resolve_member(args.name)
    currency = (args.currency or trip.base_currency).upper()
    trip.transfers.append(Transfer(
        id=new_id("pot_"), from_id=member.id, to_id=POT_ID,
        amount=to_minor(args.amount, currency), currency=currency,
        day=parse_day(args.date, trip_year(trip)) or trip.start, kind=TRANSFER_POT_IN,
        note=args.note or "회비",
    ))
    settlement = compute(trip)
    pot = settlement.pot
    return (f"{member.name} 회비 {format_money(to_minor(args.amount, currency), currency)} 입금. "
            f"공금 잔액 {format_money(pot.balance if pot else 0, trip.base_currency)}")


def cmd_transfer_add(book: Book, args) -> str:
    trip = current_trip(book)
    sender = resolve_entity(trip, args.sender)
    receiver = resolve_entity(trip, args.receiver)
    if sender == receiver:
        raise CliError("보내는 사람과 받는 사람이 같습니다")
    currency = (args.currency or trip.base_currency).upper()
    amount = to_minor(args.amount, currency)
    if amount <= 0:
        raise CliError("송금액은 0보다 커야 합니다")
    trip.transfers.append(Transfer(
        id=new_id("tr_"), from_id=sender, to_id=receiver, amount=amount,
        currency=currency, day=parse_day(args.date, trip_year(trip)) or date.today(),
        kind=TRANSFER_POT_IN if receiver == POT_ID else TRANSFER_PLAIN,
        note=args.note or "",
    ))
    compute(trip)
    return (f"기록: {trip.member_name(sender)} → {trip.member_name(receiver)} "
            f"{format_money(amount, currency)}")


def cmd_transfer_list(book: Book, args) -> str:
    trip = current_trip(book)
    if not trip.transfers:
        return "기록된 송금이 없습니다."
    rows = [[
        t.id[:8], str(t.day or "-"),
        f"{trip.member_name(t.from_id)} → {trip.member_name(t.to_id)}",
        format_money(t.amount, t.currency),
        "회비" if t.kind == TRANSFER_POT_IN else "송금",
        t.note,
    ] for t in trip.transfers]
    return table(["ID", "날짜", "내용", "금액", "구분", "메모"], rows,
                 ["left", "left", "left", "right", "left", "left"])


def cmd_transfer_remove(book: Book, args) -> str:
    trip = current_trip(book)
    matches = [t for t in trip.transfers if t.id.startswith(args.id)]
    if not matches:
        raise CliError(f"'{args.id}' 에 해당하는 송금 기록이 없습니다")
    if len(matches) > 1:
        raise CliError("여러 기록과 일치합니다")
    trip.transfers = [t for t in trip.transfers if t.id != matches[0].id]
    return "송금 기록을 삭제했습니다."


# ------------------------------------------------------------- 가져오기

def _review_and_add(trip: Trip, book: Book, parsed: list[ParsedTx], args) -> str:
    """OCR/파서 결과를 사람이 확인하고 장부에 넣는 단계.

    자동 확정하지 않는다. 잘못 읽은 금액이 그대로 정산에 들어가는 것보다
    한 번 더 묻는 쪽이 낫다.
    """
    if not parsed:
        return "가져올 거래내역이 없습니다."
    interactive = sys.stdin.isatty() and not args.yes
    added: list[Expense] = []
    skipped = 0

    for index, tx in enumerate(parsed, 1):
        currency = tx.currency or trip.base_currency
        head = (f"[{index}/{len(parsed)}] {tx.day or '날짜?'} "
                f"{format_money(tx.amount, currency) if tx.amount is not None else '금액?'} "
                f"| {tx.merchant or '가맹점?'}")
        print(head)
        if tx.warnings:
            for warning in tx.warnings:
                print(f"      ! {warning}")

        if tx.amount is None or tx.amount == 0:
            if not interactive:
                print("      → 금액을 못 읽어 건너뜁니다")
                skipped += 1
                continue
            raw = ask("      금액", "")
            if not raw:
                skipped += 1
                continue
            tx.amount = to_minor(raw, currency)

        title = tx.merchant or "이름 없는 지출"
        day = tx.day or parse_day(args.date, trip_year(trip)) or trip.start or date.today()
        payer_spec = args.payer or ""
        cat = category_mod.classify(title, book.category_hints)

        if interactive:
            action = ask("      [Enter] 등록 / e 수정 / s 건너뛰기", "")
            if action.lower() in ("s", "skip", "n"):
                skipped += 1
                continue
            if action.lower() in ("e", "edit"):
                title = ask("      내용", title) or title
                raw_amount = ask("      금액", format_money(tx.amount, currency, False))
                tx.amount = to_minor(raw_amount, currency)
                day = parse_day(ask("      날짜", str(day))) or day
                cat = ask(f"      카테고리 ({'/'.join(CATEGORIES)})", cat) or cat
            if not payer_spec:
                payer_spec = ask("      결제한 사람", trip.members[0].name if trip.members else "")

        if not payer_spec:
            raise CliError("결제한 사람을 알 수 없습니다. --payer 로 지정하세요.")
        if cat not in CATEGORIES:
            cat = "기타"

        expense = Expense(
            id=new_id("e_"), title=title, amount=tx.amount, currency=currency,
            day=day, category=cat,
            payments=parse_payers(trip, payer_spec, tx.amount, currency),
            split_method=SPLIT_EQUAL, participants=parse_members(trip, args.who),
            note=" ".join(x for x in [tx.card, tx.time] if x),
            source=args.source, image_path=getattr(args, "image_path", "") or "",
        )
        trip.expenses.append(expense)
        added.append(expense)
        print(f"      → 등록 [{expense.id[:8]}] {expense.category}")

    compute(trip)
    total = sum(e.amount for e in added if e.currency == trip.base_currency)
    lines = [f"{len(added)}건 등록, {skipped}건 건너뜀."]
    if total:
        lines.append(f"등록 합계(기준통화 건만): {format_money(total, trip.base_currency)}")
    return "\n".join(lines)


def cmd_import_text(book: Book, args) -> str:
    trip = current_trip(book)
    if args.file:
        raw = Path(args.file).read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        raw = sys.stdin.read()
    else:
        print("카드 문자·결제 알림을 붙여넣고 마지막 줄에 . 만 입력하세요:")
        lines = []
        while True:
            line = input()
            if line.strip() == ".":
                break
            lines.append(line)
        raw = "\n".join(lines)
    if not raw.strip():
        raise CliError("입력이 비어 있습니다")
    parsed = parse_text(raw, trip_year(trip))
    args.source = "text"
    return _review_and_add(trip, book, parsed, args)


def cmd_import_image(book: Book, args) -> str:
    trip = current_trip(book)
    if not ocr_claude.is_available():
        raise CliError(
            "Claude Code CLI(`claude`)를 찾을 수 없습니다.\n"
            "설치했다면 실행 경로를 TRAVEL_SETTLE_CLAUDE_CMD 환경변수로 알려주세요.\n"
            "대신 문자 내용을 복사해 `import text` 로 넣을 수도 있습니다."
        )
    year = trip_year(trip)
    results: list[str] = []
    for path in args.paths:
        print(f"이미지 분석 중: {path}")
        try:
            parsed = ocr_claude.extract(path, year)
        except ocr_claude.OcrError as exc:
            results.append(f"{path}: {exc}")
            continue
        args.source = "image"
        args.image_path = str(Path(path).resolve())
        results.append(f"{path}\n" + _review_and_add(trip, book, parsed, args))
    return "\n".join(results)


# ---------------------------------------------------------------- 정산

def cmd_settle(book: Book, args) -> str:
    trip = pick_trip(book, args.trip)
    settlement = compute(trip)
    out = [summary(settlement, show_detail=not args.brief)]
    verification = verify(settlement)
    if not verification.ok or args.verify:
        out.append("")
        out.append(verification_report(settlement, verification))
    return "\n".join(out)


def cmd_share(book: Book, args) -> str:
    trip = pick_trip(book, args.trip)
    return share_text(compute(trip))


def cmd_verify(book: Book, args) -> str:
    out = []
    if not book.trips and not args.fuzz:
        return ("검증할 여행이 없습니다. `demo` 로 예제를 만들거나 "
                "`verify --fuzz 1000` 으로 엔진 자가검사만 돌릴 수 있습니다.")
    if book.trips:
        trip = pick_trip(book, args.trip)
        settlement = compute(trip)
        out.append(verification_report(settlement))
    if args.fuzz:
        out.append("")
        out.append(rule(f"무작위 자가검사 {args.fuzz:,}건"))
        failures = []
        for seed in range(args.fuzz):
            try:
                sample = compute(random_trip(seed))
                result = verify(sample)
                extra = cross_check_total(sample)
                if not result.ok or not extra.ok:
                    codes = [c.code for c in result.failures] + ([] if extra.ok else [extra.code])
                    failures.append((seed, codes))
            except Exception as exc:  # noqa: BLE001 - 어떤 예외든 실패로 기록한다
                failures.append((seed, [type(exc).__name__ + ": " + str(exc)[:80]]))
            if failures and len(failures) >= 5:
                break
        if failures:
            for seed, codes in failures:
                out.append(f"  ✘ seed={seed}  {', '.join(codes)}")
            out.append("")
            out.append("  재현: python3 -c \"from settle.fuzz import random_trip; "
                       "from settle.engine import compute; compute(random_trip(SEED))\"")
        else:
            out.append(f"  ✔ {args.fuzz:,}건 모두 통과. 불변식이 깨지는 조합을 찾지 못했습니다.")
    return "\n".join(out)


# -------------------------------------------------------------- 내보내기

def cmd_export(book: Book, args) -> str:
    trip = pick_trip(book, args.trip)
    settlement = compute(trip)
    path = Path(args.path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "json":
        store.export_json(book, path)
        return f"JSON으로 내보냈습니다: {path}"

    if args.format == "csv":
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["날짜", "내용", "카테고리", "금액", "통화",
                             "기준통화환산", "결제자", "분할방식", "정산제외", "메모"])
            by_id = {s.expense_id: s for s in settlement.splits}
            for expense in trip.expenses:
                split = by_id.get(expense.id)
                writer.writerow([
                    expense.day or "", expense.title, expense.category,
                    expense.amount, expense.currency,
                    split.base_total if split else "",
                    " ".join(f"{trip.member_name(p.member_id)}:{p.amount}"
                             for p in expense.payments),
                    expense.split_method,
                    "Y" if expense.exclude_from_settlement else "",
                    expense.note,
                ])
            writer.writerow([])
            writer.writerow(["이름", "결제액", "부담액", "잔액"])
            for member in trip.members:
                balance = settlement.balances.get(member.id)
                if not balance:
                    continue
                writer.writerow([member.name, balance.paid, balance.owed,
                                 settlement.rounded_net.get(member.id, balance.net)])
            writer.writerow([])
            writer.writerow(["보내는 사람", "받는 사람", "금액"])
            for transfer in settlement.plan:
                writer.writerow([trip.member_name(transfer.from_id),
                                 trip.member_name(transfer.to_id), transfer.amount])
        return f"CSV로 내보냈습니다: {path}"

    raise CliError(f"알 수 없는 형식: {args.format}")


def cmd_import_file(book: Book, args) -> str:
    incoming = store.import_json(Path(args.path))
    existing = {t.id for t in book.trips}
    added = 0
    for trip in incoming.trips:
        if trip.id in existing:
            if not args.overwrite:
                continue
            book.trips = [t for t in book.trips if t.id != trip.id]
        book.trips.append(trip)
        added += 1
    book.category_hints.update(incoming.category_hints)
    return f"여행 {added}건을 가져왔습니다."


# ---------------------------------------------------------------- demo

def cmd_demo(book: Book, args) -> str:
    """실제로 일어나는 상황을 모아 놓은 예제 여행."""
    start = date(2025, 8, 28)
    trip = Trip(
        id=new_id("trip_"), name="오사카 3박4일(예제)", base_currency="KRW",
        start=start, end=start + timedelta(days=3),
        rates={"JPY": 9.2}, rounding_unit=100,
    )
    names = ["민수", "지영", "현우", "서연"]
    members = [Member(id=f"m_{i}", name=n) for i, n in enumerate(names)]
    members[3].joined = start + timedelta(days=1)   # 하루 늦게 합류
    members[2].weight = 1.0
    trip.members = members
    m = {x.name: x.id for x in members}

    # 1인 30만원씩 회비를 걷어 공금으로 쓴다
    trip.transfers += [
        Transfer(id=f"pot_{i}", from_id=mid, to_id=POT_ID, amount=300_000,
                 day=start, kind=TRANSFER_POT_IN, note="회비")
        for i, mid in enumerate([m["민수"], m["지영"], m["현우"], m["서연"]])
    ]
    trip.expenses = [
        # 서연은 하루 늦게 합류하지만 항공권은 4인 예약이므로 분담 대상을 명시한다
        Expense(id="e_1", title="대한항공 왕복", amount=1_040_000, day=start,
                category="항공/기차", payments=[Payment(m["민수"], 1_040_000)],
                participants=[m["민수"], m["지영"], m["현우"], m["서연"]],
                note="4인 예약, 서연 몫 포함"),
        Expense(id="e_2", title="난바 호텔 3박", amount=63_000, currency="JPY",
                day=start, category="숙박", payments=[Payment(POT_ID, 63_000)],
                split_method=SPLIT_WEIGHT,
                split_values={m["민수"]: 1, m["지영"]: 1, m["현우"]: 1, m["서연"]: 0.7},
                note="서연은 1박 늦게 합류"),
        Expense(id="e_3", title="이치란 라멘", amount=4_400, currency="JPY",
                day=start, category="식비", payments=[Payment(m["지영"], 4_400)]),
        Expense(id="e_4", title="이자카야", amount=18_000, currency="JPY",
                day=start + timedelta(days=1), category="주류",
                payments=[Payment(m["현우"], 12_000), Payment(m["지영"], 6_000)],
                adjustments={m["현우"]: 4_000},
                note="현우가 많이 마셔서 4천엔 더 부담"),
        Expense(id="e_5", title="유니버설 입장권", amount=33_600, currency="JPY",
                day=start + timedelta(days=2), category="관광/입장료",
                payments=[Payment(POT_ID, 33_600)]),
        Expense(id="e_6", title="지하철 IC카드 충전", amount=8_000, currency="JPY",
                day=start + timedelta(days=1), category="교통",
                payments=[Payment(m["서연"], 8_000)]),
        Expense(id="e_7", title="돈키호테 기념품", amount=12_000, currency="JPY",
                day=start + timedelta(days=2), category="쇼핑",
                payments=[Payment(m["지영"], 12_000)],
                exclude_from_settlement=True, note="지영 개인 구매"),
        Expense(id="e_8", title="공항 리무진", amount=6_000, currency="JPY",
                day=start + timedelta(days=3), category="교통",
                payments=[Payment(m["민수"], 6_000)],
                split_method=SPLIT_EXACT,
                split_values={m["민수"]: 1500, m["지영"]: 1500,
                              m["현우"]: 1500, m["서연"]: 1500}),
        Expense(id="e_9", title="호텔 미니바 환불", amount=-2_000, currency="JPY",
                day=start + timedelta(days=3), category="숙박",
                payments=[Payment(POT_ID, -2_000)]),
    ]
    trip.transfers.append(Transfer(
        id="tr_1", from_id=m["서연"], to_id=m["민수"], amount=260_000,
        day=start + timedelta(days=1), kind=TRANSFER_PLAIN, note="항공권 값 먼저 송금",
    ))
    book.trips.append(trip)
    book.current_trip_id = trip.id
    settlement = compute(trip)
    return (f"예제 여행 '{trip.name}' 을 만들었습니다.\n\n"
            + summary(settlement) + "\n\n" + verification_report(settlement))


# ------------------------------------------------------------- argparse

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="travel-settle", description="여행 정산 계산기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="예) python3 -m settle demo    /    python3 -m settle settle",
    )
    parser.add_argument("--data", help="장부 파일 경로 (기본: ~/.travel-settle/data.json)")
    parser.add_argument("--version", action="version", version=f"travel-settle {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # trip
    trip = sub.add_parser("trip", help="여행 관리").add_subparsers(dest="sub", required=True)
    p = trip.add_parser("new", help="새 여행")
    p.add_argument("name")
    p.add_argument("--start"); p.add_argument("--end")
    p.add_argument("--currency", default="KRW")
    p.add_argument("--rounding", type=int, default=1, help="송금액 반올림 단위 (예: 100)")
    p.set_defaults(func=cmd_trip_new)
    p = trip.add_parser("list", help="여행 목록"); p.set_defaults(func=cmd_trip_list)
    p = trip.add_parser("use", help="현재 여행 선택"); p.add_argument("name")
    p.set_defaults(func=cmd_trip_use)
    p = trip.add_parser("show", help="현재 여행 상세")
    p.add_argument("--limit", type=int); p.set_defaults(func=cmd_trip_show)
    p = trip.add_parser("set", help="여행 설정 변경")
    p.add_argument("--name"); p.add_argument("--start"); p.add_argument("--end")
    p.add_argument("--currency"); p.add_argument("--rounding", type=int)
    p.set_defaults(func=cmd_trip_set)
    p = trip.add_parser("delete", help="여행 삭제")
    p.add_argument("name"); p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_trip_delete)

    # member
    member = sub.add_parser("member", help="참가자 관리").add_subparsers(dest="sub", required=True)
    p = member.add_parser("add", help="참가자 추가 (여러 명 가능)")
    p.add_argument("names", nargs="+")
    p.add_argument("--weight", type=float, default=1.0, help="기본 인분 (아이 0.5 등)")
    p.add_argument("--joined", help="합류일"); p.add_argument("--left", help="이탈일")
    p.add_argument("--note", default=""); p.set_defaults(func=cmd_member_add)
    p = member.add_parser("list"); p.set_defaults(func=cmd_member_list)
    p = member.add_parser("set", help="참가자 수정")
    p.add_argument("name"); p.add_argument("--rename"); p.add_argument("--weight", type=float)
    p.add_argument("--joined"); p.add_argument("--left"); p.add_argument("--note")
    p.set_defaults(func=cmd_member_set)
    p = member.add_parser("remove"); p.add_argument("name")
    p.set_defaults(func=cmd_member_remove)

    # rate
    rate = sub.add_parser("rate", help="환율").add_subparsers(dest="sub", required=True)
    p = rate.add_parser("set"); p.add_argument("currency"); p.add_argument("rate", type=float)
    p.set_defaults(func=cmd_rate_set)
    p = rate.add_parser("list"); p.set_defaults(func=cmd_rate_list)

    # expense
    expense = sub.add_parser("expense", help="지출").add_subparsers(dest="sub", required=True)
    p = expense.add_parser("add", help="지출 등록 (인자를 생략하면 물어봅니다)")
    p.add_argument("--title"); p.add_argument("--amount")
    p.add_argument("--payer", help="'민수' 또는 '민수:60000,지영:30000' 또는 '공금'")
    p.add_argument("--date"); p.add_argument("--category")
    p.add_argument("--split", choices=SPLIT_METHODS, default=SPLIT_EQUAL)
    p.add_argument("--who", help="분담할 사람 (쉼표). 생략하면 그날 참여 중인 전원")
    p.add_argument("--values", help="weight/percent/exact 값: '민수=2,지영=1'")
    p.add_argument("--extra", help="더 내기로 한 금액: '민수=20000'")
    p.add_argument("--currency"); p.add_argument("--rate", type=float)
    p.add_argument("--personal", action="store_true", help="개인 지출 (정산 제외)")
    p.add_argument("--note"); p.add_argument("--image", default="")
    p.set_defaults(func=cmd_expense_add, source="manual")
    p = expense.add_parser("list"); p.add_argument("--limit", type=int)
    p.set_defaults(func=cmd_expense_list)
    p = expense.add_parser("show"); p.add_argument("id"); p.set_defaults(func=cmd_expense_show)
    p = expense.add_parser("edit"); p.add_argument("id")
    p.add_argument("--title"); p.add_argument("--amount"); p.add_argument("--payer")
    p.add_argument("--date"); p.add_argument("--category")
    p.add_argument("--split", choices=SPLIT_METHODS); p.add_argument("--who")
    p.add_argument("--values"); p.add_argument("--extra"); p.add_argument("--note")
    p.add_argument("--currency")
    p.add_argument("--personal", action=argparse.BooleanOptionalAction, default=None)
    p.set_defaults(func=cmd_expense_edit)
    p = expense.add_parser("remove"); p.add_argument("id")
    p.add_argument("--yes", action="store_true"); p.set_defaults(func=cmd_expense_remove)

    # pot / transfer
    pot = sub.add_parser("pot", help="공금(회비)").add_subparsers(dest="sub", required=True)
    p = pot.add_parser("in", help="회비 입금")
    p.add_argument("name"); p.add_argument("amount")
    p.add_argument("--date"); p.add_argument("--currency"); p.add_argument("--note")
    p.set_defaults(func=cmd_pot_in)

    transfer = sub.add_parser("transfer", help="이미 주고받은 돈").add_subparsers(dest="sub", required=True)
    p = transfer.add_parser("add"); p.add_argument("sender"); p.add_argument("receiver")
    p.add_argument("amount"); p.add_argument("--date"); p.add_argument("--currency")
    p.add_argument("--note"); p.set_defaults(func=cmd_transfer_add)
    p = transfer.add_parser("list"); p.set_defaults(func=cmd_transfer_list)
    p = transfer.add_parser("remove"); p.add_argument("id")
    p.set_defaults(func=cmd_transfer_remove)

    # import
    imp = sub.add_parser("import", help="거래내역 가져오기").add_subparsers(dest="sub", required=True)
    p = imp.add_parser("text", help="카드 문자·결제 알림 붙여넣기")
    p.add_argument("--file"); p.add_argument("--payer"); p.add_argument("--who")
    p.add_argument("--date"); p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_import_text, source="text")
    p = imp.add_parser("image", help="캡쳐 이미지에서 추출 (Claude Code CLI 사용)")
    p.add_argument("paths", nargs="+"); p.add_argument("--payer"); p.add_argument("--who")
    p.add_argument("--date"); p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_import_image, source="image")
    p = imp.add_parser("json", help="내보낸 JSON 되돌리기")
    p.add_argument("path"); p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_import_file)

    # 정산 / 검증 / 내보내기
    p = sub.add_parser("settle", help="정산 결과")
    p.add_argument("--trip"); p.add_argument("--brief", action="store_true")
    p.add_argument("--verify", action="store_true", help="검증 결과도 함께 표시")
    p.set_defaults(func=cmd_settle)
    p = sub.add_parser("share", help="메신저에 붙여넣을 요약")
    p.add_argument("--trip"); p.set_defaults(func=cmd_share)
    p = sub.add_parser("verify", help="폐루프 검증")
    p.add_argument("--trip")
    p.add_argument("--fuzz", type=int, default=0, help="무작위 여행 N건으로 자가검사")
    p.set_defaults(func=cmd_verify)
    p = sub.add_parser("export", help="내보내기")
    p.add_argument("format", choices=["json", "csv"]); p.add_argument("path")
    p.add_argument("--trip"); p.set_defaults(func=cmd_export)
    p = sub.add_parser("demo", help="예제 여행 만들기")
    p.set_defaults(func=cmd_demo)
    return parser


READ_ONLY = {cmd_trip_list, cmd_trip_show, cmd_member_list, cmd_rate_list,
             cmd_expense_list, cmd_expense_show, cmd_transfer_list,
             cmd_settle, cmd_share, cmd_verify, cmd_export}


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    path = Path(args.data) if args.data else None
    try:
        book = store.load(path)
        output = args.func(book, args)
        if args.func not in READ_ONLY:
            store.save(book, path)
        if output:
            print(output)
        return 0
    except (CliError, InputError, SettleError, KeyError, ValueError) as exc:
        message = exc.args[0] if exc.args else str(exc)
        print(f"오류: {message}", file=sys.stderr)
        return 1
    except ocr_claude.OcrError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n중단했습니다.", file=sys.stderr)
        return 130
