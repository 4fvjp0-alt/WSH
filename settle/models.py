"""데이터 모델과 JSON 직렬화."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

SCHEMA_VERSION = 1

# 공금(회비)은 "가상 멤버"로 모델링한다. 회비 입금은 멤버 -> 공금 송금이고,
# 공금 결제는 공금이 결제자인 지출이다. 그러면 남은 공금 환급까지 최종
# 송금안에서 자동으로 계산된다.
POT_ID = "__pot__"
POT_NAME = "공금"

SPLIT_EQUAL = "equal"      # 균등 분할
SPLIT_WEIGHT = "weight"    # 가중치(인분) 분할
SPLIT_EXACT = "exact"      # 금액 직접 지정
SPLIT_PERCENT = "percent"  # 비율(%) 분할
SPLIT_METHODS = (SPLIT_EQUAL, SPLIT_WEIGHT, SPLIT_EXACT, SPLIT_PERCENT)

CATEGORIES = [
    "식비", "카페/간식", "주류", "숙박", "교통", "항공/기차",
    "관광/입장료", "쇼핑", "통신", "의료", "기타",
]

TRANSFER_PLAIN = "transfer"   # 일반 송금 (중간 정산)
TRANSFER_POT_IN = "pot_in"    # 회비 입금 (멤버 -> 공금)
TRANSFER_KINDS = (TRANSFER_PLAIN, TRANSFER_POT_IN)


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def _iso(value: Optional[date]) -> Optional[str]:
    return value.isoformat() if value else None


def _parse_date(value) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


@dataclass
class Member:
    id: str
    name: str
    weight: float = 1.0          # 기본 인분 (아이 0.5 등)
    joined: Optional[date] = None  # 참여 시작일 (None = 여행 시작부터)
    left: Optional[date] = None    # 참여 종료일 (None = 끝까지)
    note: str = ""

    def is_active_on(self, day: Optional[date]) -> bool:
        if day is None:
            return True
        if self.joined and day < self.joined:
            return False
        if self.left and day > self.left:
            return False
        return True

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "weight": self.weight,
            "joined": _iso(self.joined), "left": _iso(self.left), "note": self.note,
        }

    @staticmethod
    def from_dict(d: dict) -> "Member":
        return Member(
            id=d["id"], name=d["name"], weight=float(d.get("weight", 1.0)),
            joined=_parse_date(d.get("joined")), left=_parse_date(d.get("left")),
            note=d.get("note", ""),
        )


@dataclass
class Payment:
    """한 지출을 실제로 결제한 사람과 금액 (지출 통화 최소단위)."""
    member_id: str
    amount: int

    def to_dict(self) -> dict:
        return {"member_id": self.member_id, "amount": self.amount}

    @staticmethod
    def from_dict(d: dict) -> "Payment":
        return Payment(member_id=d["member_id"], amount=int(d["amount"]))


@dataclass
class Expense:
    id: str
    title: str
    amount: int                                  # 지출 통화 최소단위
    currency: str = "KRW"
    day: Optional[date] = None
    category: str = "기타"
    payments: list[Payment] = field(default_factory=list)
    split_method: str = SPLIT_EQUAL
    participants: list[str] = field(default_factory=list)   # 비어 있으면 그날 참여 중인 전원
    split_values: dict[str, float] = field(default_factory=dict)
    adjustments: dict[str, int] = field(default_factory=dict)  # "더 내기로 한 금액"(지출 통화)
    rate: Optional[float] = None                 # 이 건에만 적용할 환율 (없으면 여행 환율표)
    exclude_from_settlement: bool = False        # 개인 지출: 통계엔 남기고 정산에선 제외
    note: str = ""
    source: str = "manual"                       # manual | text | image
    image_path: str = ""
    created_at: str = ""

    @property
    def total_paid(self) -> int:
        return sum(p.amount for p in self.payments)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title, "amount": self.amount,
            "currency": self.currency, "day": _iso(self.day), "category": self.category,
            "payments": [p.to_dict() for p in self.payments],
            "split_method": self.split_method, "participants": list(self.participants),
            "split_values": dict(self.split_values), "adjustments": dict(self.adjustments),
            "rate": self.rate, "exclude_from_settlement": self.exclude_from_settlement,
            "note": self.note, "source": self.source, "image_path": self.image_path,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(d: dict) -> "Expense":
        return Expense(
            id=d["id"], title=d.get("title", ""), amount=int(d["amount"]),
            currency=d.get("currency", "KRW"), day=_parse_date(d.get("day")),
            category=d.get("category", "기타"),
            payments=[Payment.from_dict(p) for p in d.get("payments", [])],
            split_method=d.get("split_method", SPLIT_EQUAL),
            participants=list(d.get("participants", [])),
            split_values={k: float(v) for k, v in (d.get("split_values") or {}).items()},
            adjustments={k: int(v) for k, v in (d.get("adjustments") or {}).items()},
            rate=d.get("rate"),
            exclude_from_settlement=bool(d.get("exclude_from_settlement", False)),
            note=d.get("note", ""), source=d.get("source", "manual"),
            image_path=d.get("image_path", ""), created_at=d.get("created_at", ""),
        )


@dataclass
class Transfer:
    """이미 오간 돈. 여행 중 중간 송금과 회비 입금을 같은 구조로 다룬다."""
    id: str
    from_id: str
    to_id: str
    amount: int
    currency: str = "KRW"
    day: Optional[date] = None
    kind: str = TRANSFER_PLAIN
    rate: Optional[float] = None
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "from_id": self.from_id, "to_id": self.to_id,
            "amount": self.amount, "currency": self.currency, "day": _iso(self.day),
            "kind": self.kind, "rate": self.rate, "note": self.note,
        }

    @staticmethod
    def from_dict(d: dict) -> "Transfer":
        return Transfer(
            id=d["id"], from_id=d["from_id"], to_id=d["to_id"], amount=int(d["amount"]),
            currency=d.get("currency", "KRW"), day=_parse_date(d.get("day")),
            kind=d.get("kind", TRANSFER_PLAIN), rate=d.get("rate"), note=d.get("note", ""),
        )


@dataclass
class Trip:
    id: str
    name: str
    base_currency: str = "KRW"
    start: Optional[date] = None
    end: Optional[date] = None
    members: list[Member] = field(default_factory=list)
    expenses: list[Expense] = field(default_factory=list)
    transfers: list[Transfer] = field(default_factory=list)
    rates: dict[str, float] = field(default_factory=dict)  # 통화 -> 기준통화 환율
    rounding_unit: int = 1                                  # 송금액 반올림 단위
    note: str = ""

    # --- 조회 헬퍼 -------------------------------------------------
    def member(self, member_id: str) -> Optional[Member]:
        for m in self.members:
            if m.id == member_id:
                return m
        return None

    def member_name(self, member_id: str) -> str:
        if member_id == POT_ID:
            return POT_NAME
        m = self.member(member_id)
        return m.name if m else f"<알 수 없음:{member_id}>"

    def find_members(self, query: str) -> list[Member]:
        q = query.strip().lower()
        exact = [m for m in self.members if m.name.lower() == q or m.id == query]
        if exact:
            return exact
        return [m for m in self.members if q and q in m.name.lower()]

    def resolve_member(self, query: str) -> Member:
        if query in (POT_ID, POT_NAME, "공금", "회비"):
            raise KeyError("공금은 일반 멤버로 지정할 수 없습니다")
        found = self.find_members(query)
        if not found:
            raise KeyError(f"'{query}' 에 해당하는 멤버가 없습니다")
        if len(found) > 1:
            names = ", ".join(m.name for m in found)
            raise KeyError(f"'{query}' 가 여러 명과 일치합니다: {names}")
        return found[0]

    def active_members_on(self, day: Optional[date]) -> list[Member]:
        active = [m for m in self.members if m.is_active_on(day)]
        return active if active else list(self.members)

    def expense(self, expense_id: str) -> Optional[Expense]:
        for e in self.expenses:
            if e.id == expense_id:
                return e
        return None

    def uses_pot(self) -> bool:
        if any(t.kind == TRANSFER_POT_IN for t in self.transfers):
            return True
        return any(p.member_id == POT_ID for e in self.expenses for p in e.payments)

    # --- 직렬화 ----------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "base_currency": self.base_currency,
            "start": _iso(self.start), "end": _iso(self.end),
            "members": [m.to_dict() for m in self.members],
            "expenses": [e.to_dict() for e in self.expenses],
            "transfers": [t.to_dict() for t in self.transfers],
            "rates": dict(self.rates), "rounding_unit": self.rounding_unit,
            "note": self.note,
        }

    @staticmethod
    def from_dict(d: dict) -> "Trip":
        return Trip(
            id=d["id"], name=d.get("name", ""),
            base_currency=d.get("base_currency", "KRW"),
            start=_parse_date(d.get("start")), end=_parse_date(d.get("end")),
            members=[Member.from_dict(m) for m in d.get("members", [])],
            expenses=[Expense.from_dict(e) for e in d.get("expenses", [])],
            transfers=[Transfer.from_dict(t) for t in d.get("transfers", [])],
            rates={k: float(v) for k, v in (d.get("rates") or {}).items()},
            rounding_unit=int(d.get("rounding_unit", 1)), note=d.get("note", ""),
        )


@dataclass
class Book:
    """여러 여행을 담는 최상위 저장 단위."""
    trips: list[Trip] = field(default_factory=list)
    current_trip_id: Optional[str] = None
    category_hints: dict[str, str] = field(default_factory=dict)  # 가맹점명 -> 카테고리 학습
    version: int = SCHEMA_VERSION

    def trip(self, trip_id: str) -> Optional[Trip]:
        for t in self.trips:
            if t.id == trip_id:
                return t
        return None

    def find_trips(self, query: str) -> list[Trip]:
        q = query.strip().lower()
        exact = [t for t in self.trips if t.name.lower() == q or t.id == query]
        if exact:
            return exact
        return [t for t in self.trips if q and q in t.name.lower()]

    def current(self) -> Optional[Trip]:
        if self.current_trip_id:
            found = self.trip(self.current_trip_id)
            if found:
                return found
        return self.trips[-1] if self.trips else None

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "current_trip_id": self.current_trip_id,
            "category_hints": dict(self.category_hints),
            "trips": [t.to_dict() for t in self.trips],
        }

    @staticmethod
    def from_dict(d: dict) -> "Book":
        return Book(
            trips=[Trip.from_dict(t) for t in d.get("trips", [])],
            current_trip_id=d.get("current_trip_id"),
            category_hints=dict(d.get("category_hints") or {}),
            version=int(d.get("version", SCHEMA_VERSION)),
        )


def migrate(raw: dict[str, Any]) -> dict[str, Any]:
    """저장 파일 스키마 마이그레이션. 지금은 버전 1만 존재한다."""
    version = int(raw.get("version", SCHEMA_VERSION))
    if version > SCHEMA_VERSION:
        raise ValueError(
            f"저장 파일 버전({version})이 프로그램이 아는 버전({SCHEMA_VERSION})보다 높습니다. "
            "프로그램을 업데이트하세요."
        )
    raw["version"] = SCHEMA_VERSION
    return raw
