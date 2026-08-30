"""화면과 정산 엔진 사이의 얇은 API 계층.

HTTP와 분리해 둔 이유는 두 가지다. 소켓 없이 테스트할 수 있고, 나중에
데스크톱 앱이나 모바일로 갈 때 이 계층을 그대로 재사용할 수 있다.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable, Optional

from . import category as category_mod
from .cliutil import parse_day
from .engine import Settlement, compute
from .invariants import cross_check_total, verify
from .models import (
    CATEGORIES, POT_ID, POT_NAME, SPLIT_EQUAL, SPLIT_EXACT, SPLIT_METHODS,
    TRANSFER_PLAIN, TRANSFER_POT_IN, Book, Expense, Member, Payment, Transfer,
    Trip, new_id,
)
from .money import MINOR_DIGITS, format_money, minor_digits, to_minor
from .parse_text import parse_text
from .report import share_text
from .split import SettleError


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _need(payload: dict, key: str) -> Any:
    value = payload.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ApiError(f"'{key}' 값이 필요합니다")
    return value


def _trip(book: Book) -> Trip:
    trip = book.current()
    if trip is None:
        raise ApiError("먼저 여행을 만드세요", 404)
    return trip


def _trip_year(trip: Trip) -> int:
    return (trip.start or trip.end or date.today()).year


def _member(trip: Trip, member_id: str) -> Member:
    member = trip.member(member_id)
    if member is None:
        raise ApiError(f"참가자를 찾을 수 없습니다: {member_id}", 404)
    return member


# --------------------------------------------------------------- 직렬화

def _member_dict(trip: Trip, member: Member) -> dict:
    return {
        "id": member.id, "name": member.name, "weight": member.weight,
        "joined": member.joined.isoformat() if member.joined else None,
        "left": member.left.isoformat() if member.left else None,
        "note": member.note,
    }


def _expense_dict(trip: Trip, expense: Expense, base_total: Optional[int]) -> dict:
    return {
        "id": expense.id,
        "title": expense.title,
        "amount": expense.amount,
        "currency": expense.currency,
        "base_total": base_total,
        "day": expense.day.isoformat() if expense.day else None,
        "category": expense.category,
        "payments": [{"member_id": p.member_id,
                      "name": trip.member_name(p.member_id),
                      "amount": p.amount} for p in expense.payments],
        "split_method": expense.split_method,
        "participants": list(expense.participants),
        "split_values": dict(expense.split_values),
        "adjustments": dict(expense.adjustments),
        "rate": expense.rate,
        "personal": expense.exclude_from_settlement,
        "note": expense.note,
        "source": expense.source,
    }


def _settlement_dict(settlement: Settlement) -> dict:
    trip = settlement.trip
    balances = []
    for member in trip.members:
        balance = settlement.balances.get(member.id)
        if balance is None:
            continue
        balances.append({
            "member_id": member.id, "name": member.name,
            "paid": balance.paid, "owed": balance.owed,
            "personal": balance.personal,
            "net": settlement.rounded_net.get(member.id, balance.net),
        })
    pot = None
    if settlement.pot is not None:
        pot = {
            "contributed": settlement.pot.contributed,
            "spent": settlement.pot.spent,
            "balance": settlement.pot.balance,
            "per_member": [{"name": trip.member_name(mid), "amount": amount}
                           for mid, amount in sorted(settlement.pot.per_member.items(),
                                                     key=lambda kv: -kv[1])],
        }
    return {
        "total": settlement.total,
        "personal_total": settlement.personal_total,
        "per_head": settlement.total // len(trip.members) if trip.members else 0,
        "balances": balances,
        "plan": [{"from_id": t.from_id, "to_id": t.to_id,
                  "from": trip.member_name(t.from_id),
                  "to": trip.member_name(t.to_id),
                  "amount": t.amount} for t in settlement.plan],
        "by_category": sorted(
            [{"name": k, "amount": v} for k, v in settlement.by_category.items()],
            key=lambda x: -x["amount"]),
        "by_day": sorted(
            [{"name": k, "amount": v} for k, v in settlement.by_day.items()],
            key=lambda x: x["name"]),
        "by_currency": sorted(
            [{"name": k, "amount": v} for k, v in settlement.by_currency.items()],
            key=lambda x: x["name"]),
        "pot": pot,
        "warnings": list(settlement.warnings),
    }


def _verification_dict(settlement: Settlement) -> dict:
    result = verify(settlement)
    checks = [{"code": c.code, "title": c.title, "ok": c.ok, "detail": c.detail}
              for c in result.checks]
    extra = cross_check_total(settlement)
    checks.append({"code": extra.code, "title": extra.title,
                   "ok": extra.ok, "detail": extra.detail})
    return {"ok": all(c["ok"] for c in checks), "checks": checks}


def _state(book: Book) -> dict:
    trips = [{
        "id": t.id, "name": t.name,
        "start": t.start.isoformat() if t.start else None,
        "end": t.end.isoformat() if t.end else None,
        "members": len(t.members), "expenses": len(t.expenses),
        "currency": t.base_currency,
    } for t in book.trips]
    current = book.current()
    if current is None:
        return {"trips": trips, "trip": None, "categories": CATEGORIES,
                "minor_digits": {}, "pot_name": POT_NAME, "pot_id": POT_ID,
                "split_methods": list(SPLIT_METHODS)}

    settlement = compute(current)
    base_by_id = {s.expense_id: s.base_total for s in settlement.splits}
    # 화면이 금액을 제대로 찍으려면 통화별 소수 자릿수를 알아야 한다.
    # 여행에 이미 쓰인 통화만 보내면, 문자에서 새로 인식된 통화(예: 첫 엔화 결제)를
    # 화면이 소수 두 자리로 착각해 3,200엔을 32엔으로 만든다. 표 전체를 보낸다.
    currencies = (set(MINOR_DIGITS) | {current.base_currency}
                  | {e.currency for e in current.expenses}
                  | {t.currency for t in current.transfers})
    return {
        "trips": trips,
        "trip": {
            "id": current.id, "name": current.name,
            "start": current.start.isoformat() if current.start else None,
            "end": current.end.isoformat() if current.end else None,
            "currency": current.base_currency,
            "rounding_unit": current.rounding_unit,
            "rates": dict(current.rates),
            "members": [_member_dict(current, m) for m in current.members],
        },
        "expenses": [_expense_dict(current, e, base_by_id.get(e.id))
                     for e in sorted(current.expenses,
                                     key=lambda e: (e.day or date.min, e.id),
                                     reverse=True)],
        "transfers": [{
            "id": t.id, "from_id": t.from_id, "to_id": t.to_id,
            "from": current.member_name(t.from_id), "to": current.member_name(t.to_id),
            "amount": t.amount, "currency": t.currency,
            "day": t.day.isoformat() if t.day else None,
            "kind": t.kind, "note": t.note,
        } for t in current.transfers],
        "settlement": _settlement_dict(settlement),
        "verification": _verification_dict(settlement),
        "categories": CATEGORIES,
        "split_methods": list(SPLIT_METHODS),
        "minor_digits": {c: minor_digits(c) for c in sorted(currencies)},
        "pot_name": POT_NAME,
        "pot_id": POT_ID,
    }


# ------------------------------------------------------------------ 여행

def _trip_new(book: Book, payload: dict) -> dict:
    trip = Trip(
        id=new_id("trip_"), name=str(_need(payload, "name")).strip(),
        base_currency=str(payload.get("currency") or "KRW").upper(),
        start=parse_day(payload.get("start")), end=parse_day(payload.get("end")),
        rounding_unit=max(1, int(payload.get("rounding") or 1)),
    )
    book.trips.append(trip)
    book.current_trip_id = trip.id
    return {"id": trip.id}


def _trip_use(book: Book, payload: dict) -> dict:
    trip_id = str(_need(payload, "id"))
    if book.trip(trip_id) is None:
        raise ApiError("여행을 찾을 수 없습니다", 404)
    book.current_trip_id = trip_id
    return {"id": trip_id}


def _trip_update(book: Book, payload: dict) -> dict:
    trip = _trip(book)
    if payload.get("name"):
        trip.name = str(payload["name"]).strip()
    if "start" in payload:
        trip.start = parse_day(payload.get("start"))
    if "end" in payload:
        trip.end = parse_day(payload.get("end"))
    if payload.get("currency"):
        trip.base_currency = str(payload["currency"]).upper()
    if payload.get("rounding") is not None:
        trip.rounding_unit = max(1, int(payload["rounding"]))
    return {"id": trip.id}


def _trip_delete(book: Book, payload: dict) -> dict:
    trip_id = str(_need(payload, "id"))
    if book.trip(trip_id) is None:
        raise ApiError("여행을 찾을 수 없습니다", 404)
    book.trips = [t for t in book.trips if t.id != trip_id]
    if book.current_trip_id == trip_id:
        book.current_trip_id = book.trips[-1].id if book.trips else None
    return {"ok": True}


# ---------------------------------------------------------------- 참가자

def _member_add(book: Book, payload: dict) -> dict:
    trip = _trip(book)
    names = payload.get("names")
    if isinstance(names, str):
        names = [n for n in names.replace(",", " ").split() if n]
    if not names:
        names = [str(_need(payload, "name"))]
    year = _trip_year(trip)
    added = []
    for raw in names:
        name = str(raw).strip()
        if not name:
            continue
        if any(m.name == name for m in trip.members):
            raise ApiError(f"'{name}' 은(는) 이미 있습니다")
        member = Member(
            id=new_id("m_"), name=name,
            weight=float(payload.get("weight") or 1.0),
            joined=parse_day(payload.get("joined"), year),
            left=parse_day(payload.get("left"), year),
        )
        trip.members.append(member)
        added.append(member.id)
    if not added:
        raise ApiError("추가할 이름이 없습니다")
    return {"ids": added}


def _member_update(book: Book, payload: dict) -> dict:
    trip = _trip(book)
    member = _member(trip, str(_need(payload, "id")))
    year = _trip_year(trip)
    if payload.get("name"):
        member.name = str(payload["name"]).strip()
    if payload.get("weight") is not None:
        member.weight = float(payload["weight"])
    if "joined" in payload:
        member.joined = parse_day(payload.get("joined"), year)
    if "left" in payload:
        member.left = parse_day(payload.get("left"), year)
    return {"id": member.id}


def _member_remove(book: Book, payload: dict) -> dict:
    trip = _trip(book)
    member = _member(trip, str(_need(payload, "id")))
    used = [e for e in trip.expenses
            if any(p.member_id == member.id for p in e.payments)
            or member.id in e.participants or member.id in e.adjustments
            or member.id in e.split_values]
    used += [t for t in trip.transfers if member.id in (t.from_id, t.to_id)]
    if used:
        raise ApiError(
            f"{member.name} 은(는) 지출·송금 {len(used)}건에 걸려 있어 뺄 수 없습니다. "
            "해당 기록을 먼저 정리하세요.")
    trip.members = [m for m in trip.members if m.id != member.id]
    return {"ok": True}


def _rate_set(book: Book, payload: dict) -> dict:
    trip = _trip(book)
    code = str(_need(payload, "currency")).upper()
    if code == trip.base_currency:
        raise ApiError("기준통화에는 환율이 필요 없습니다")
    trip.rates[code] = float(_need(payload, "rate"))
    return {"currency": code, "rate": trip.rates[code]}


# ------------------------------------------------------------------ 지출

def _build_payments(trip: Trip, payload: dict, amount: int, currency: str) -> list[Payment]:
    raw = payload.get("payments")
    if raw:
        payments = [Payment(member_id=str(p["member_id"]),
                            amount=to_minor(p["amount"], currency)) for p in raw]
        total = sum(p.amount for p in payments)
        if total != amount:
            raise ApiError(
                f"결제액 합계({format_money(total, currency)})가 "
                f"지출 금액({format_money(amount, currency)})과 다릅니다")
        return payments
    payer = payload.get("payer_id")
    if not payer:
        raise ApiError("결제한 사람을 지정하세요")
    return [Payment(member_id=str(payer), amount=amount)]


def _apply_expense_fields(trip: Trip, book: Book, expense: Expense, payload: dict) -> None:
    currency = str(payload.get("currency") or expense.currency or trip.base_currency).upper()
    expense.currency = currency
    expense.title = str(payload.get("title") or expense.title or "").strip()
    if not expense.title:
        raise ApiError("내용을 입력하세요")
    if payload.get("amount") is not None:
        expense.amount = to_minor(payload["amount"], currency)
    if expense.amount == 0:
        raise ApiError("금액이 0입니다")

    expense.day = parse_day(payload.get("day"), _trip_year(trip)) or expense.day \
        or trip.start or date.today()

    category = str(payload.get("category") or expense.category or "기타")
    if category not in CATEGORIES:
        raise ApiError(f"알 수 없는 카테고리: {category}")
    if category != category_mod.classify(expense.title, book.category_hints):
        category_mod.learn(book.category_hints, expense.title, category)
    expense.category = category

    method = str(payload.get("split_method") or expense.split_method or SPLIT_EQUAL)
    if method not in SPLIT_METHODS:
        raise ApiError(f"알 수 없는 분할 방식: {method}")
    expense.split_method = method
    if "participants" in payload:
        expense.participants = [str(p) for p in (payload.get("participants") or [])]
    if "split_values" in payload:
        values = payload.get("split_values") or {}
        if method == SPLIT_EXACT:
            expense.split_values = {k: float(to_minor(v, currency))
                                    for k, v in values.items()}
        else:
            expense.split_values = {k: float(v) for k, v in values.items()}
    if "adjustments" in payload:
        expense.adjustments = {k: to_minor(v, currency)
                               for k, v in (payload.get("adjustments") or {}).items()
                               if str(v).strip() not in ("", "0")}
    if "rate" in payload:
        expense.rate = float(payload["rate"]) if payload["rate"] else None
    if "personal" in payload:
        expense.exclude_from_settlement = bool(payload["personal"])
    if "note" in payload:
        expense.note = str(payload.get("note") or "")
    expense.payments = _build_payments(trip, payload, expense.amount, currency)


def _expense_add(book: Book, payload: dict) -> dict:
    trip = _trip(book)
    if not trip.members:
        raise ApiError("참가자를 먼저 추가하세요")
    expense = Expense(id=new_id("e_"), title="", amount=0,
                      source=str(payload.get("source") or "gui"))
    _apply_expense_fields(trip, book, expense, payload)
    trip.expenses.append(expense)
    compute(trip)      # 잘못된 입력이면 여기서 걸린다
    return {"id": expense.id}


def _expense_update(book: Book, payload: dict) -> dict:
    trip = _trip(book)
    expense = trip.expense(str(_need(payload, "id")))
    if expense is None:
        raise ApiError("지출을 찾을 수 없습니다", 404)
    backup = Expense.from_dict(expense.to_dict())
    try:
        _apply_expense_fields(trip, book, expense, payload)
        compute(trip)
    except (ApiError, SettleError, ValueError):
        index = trip.expenses.index(expense)
        trip.expenses[index] = backup   # 실패하면 원래대로 되돌린다
        raise
    return {"id": expense.id}


def _expense_remove(book: Book, payload: dict) -> dict:
    trip = _trip(book)
    expense_id = str(_need(payload, "id"))
    if trip.expense(expense_id) is None:
        raise ApiError("지출을 찾을 수 없습니다", 404)
    trip.expenses = [e for e in trip.expenses if e.id != expense_id]
    return {"ok": True}


# ------------------------------------------------------------ 송금 / 공금

def _transfer_add(book: Book, payload: dict) -> dict:
    trip = _trip(book)
    sender = str(_need(payload, "from_id"))
    receiver = str(_need(payload, "to_id"))
    if sender == receiver:
        raise ApiError("보내는 사람과 받는 사람이 같습니다")
    currency = str(payload.get("currency") or trip.base_currency).upper()
    amount = to_minor(_need(payload, "amount"), currency)
    if amount <= 0:
        raise ApiError("송금액은 0보다 커야 합니다")
    transfer = Transfer(
        id=new_id("tr_"), from_id=sender, to_id=receiver, amount=amount,
        currency=currency, day=parse_day(payload.get("day"), _trip_year(trip)) or date.today(),
        kind=TRANSFER_POT_IN if receiver == POT_ID else TRANSFER_PLAIN,
        note=str(payload.get("note") or ""),
    )
    trip.transfers.append(transfer)
    compute(trip)
    return {"id": transfer.id}


def _transfer_remove(book: Book, payload: dict) -> dict:
    trip = _trip(book)
    transfer_id = str(_need(payload, "id"))
    if not any(t.id == transfer_id for t in trip.transfers):
        raise ApiError("송금 기록을 찾을 수 없습니다", 404)
    trip.transfers = [t for t in trip.transfers if t.id != transfer_id]
    return {"ok": True}


# ------------------------------------------------------------- 문자 인식

def _parse(book: Book, payload: dict) -> dict:
    trip = _trip(book)
    text = str(payload.get("text") or "")
    if not text.strip():
        raise ApiError("붙여넣은 내용이 없습니다")
    items = []
    for tx in parse_text(text, _trip_year(trip), trip.base_currency):
        items.append({
            "amount": tx.amount,
            "currency": tx.currency,
            "merchant": tx.merchant,
            "day": tx.day.isoformat() if tx.day else None,
            "time": tx.time,
            "card": tx.card,
            "installment": tx.installment,
            "is_refund": tx.is_refund,
            "converted_amount": tx.converted_amount,
            "converted_currency": tx.converted_currency,
            "rate": tx.implied_rate,
            "category": category_mod.classify(tx.merchant, book.category_hints),
            "note": tx.note,
            "warnings": list(tx.warnings),
            "ok": tx.ok,
        })
    return {"items": items}


def _import(book: Book, payload: dict) -> dict:
    trip = _trip(book)
    items = payload.get("items") or []
    if not items:
        raise ApiError("등록할 항목이 없습니다")
    created, skipped = [], []
    for item in items:
        currency = str(item.get("currency") or trip.base_currency).upper()
        rate = item.get("rate")
        if currency != trip.base_currency and not rate and currency not in trip.rates:
            skipped.append(f"{item.get('merchant') or '이름 없음'}: "
                           f"{currency} 환율이 없습니다")
            continue
        try:
            created.append(_expense_add(book, {
                "title": item.get("merchant") or "이름 없는 지출",
                "amount": item.get("amount"),
                "currency": currency,
                "day": item.get("day"),
                "category": item.get("category") or "기타",
                "payer_id": item.get("payer_id"),
                "payments": item.get("payments"),
                "participants": item.get("participants") or [],
                "rate": rate,
                "note": item.get("note") or "",
                "source": item.get("source") or "text",
            })["id"])
        except (ApiError, SettleError, ValueError) as exc:
            skipped.append(f"{item.get('merchant') or '이름 없음'}: {exc}")
    return {"added": len(created), "skipped": skipped}


def _share(book: Book, payload: dict) -> dict:
    return {"text": share_text(compute(_trip(book)))}


def _demo(book: Book, payload: dict) -> dict:
    from .cli import cmd_demo

    class _Args:
        pass

    cmd_demo(book, _Args())
    return {"id": book.current_trip_id}


ROUTES: dict[tuple[str, str], Callable[[Book, dict], dict]] = {
    ("POST", "/api/trip/new"): _trip_new,
    ("POST", "/api/trip/use"): _trip_use,
    ("POST", "/api/trip/update"): _trip_update,
    ("POST", "/api/trip/delete"): _trip_delete,
    ("POST", "/api/member/add"): _member_add,
    ("POST", "/api/member/update"): _member_update,
    ("POST", "/api/member/remove"): _member_remove,
    ("POST", "/api/rate/set"): _rate_set,
    ("POST", "/api/expense/add"): _expense_add,
    ("POST", "/api/expense/update"): _expense_update,
    ("POST", "/api/expense/remove"): _expense_remove,
    ("POST", "/api/transfer/add"): _transfer_add,
    ("POST", "/api/transfer/remove"): _transfer_remove,
    ("POST", "/api/parse"): _parse,
    ("POST", "/api/import"): _import,
    ("POST", "/api/share"): _share,
    ("POST", "/api/demo"): _demo,
}

# 장부를 바꾸지 않는 요청. 저장을 건너뛴다.
READ_ONLY = {"/api/state", "/api/parse", "/api/share"}


def handle(book: Book, method: str, path: str, payload: dict | None = None) -> dict:
    """(book, 메서드, 경로, 본문) -> 응답 dict. 실패는 ApiError."""
    payload = payload or {}
    if method == "GET" and path == "/api/state":
        return _state(book)
    route = ROUTES.get((method, path))
    if route is None:
        raise ApiError(f"알 수 없는 요청: {method} {path}", 404)
    try:
        result = route(book, payload)
    except ApiError:
        raise
    except SettleError as exc:
        raise ApiError(str(exc)) from exc
    except KeyError as exc:
        raise ApiError(exc.args[0] if exc.args else str(exc), 404) from exc
    except (ValueError, TypeError) as exc:
        raise ApiError(str(exc)) from exc
    # 변경 후 상태를 함께 돌려주면 화면이 한 번의 왕복으로 갱신된다
    result["state"] = _state(book)
    return result
