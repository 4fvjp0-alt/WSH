"""카드 승인 문자·간편결제 알림·은행 거래내역 텍스트 파서.

캡쳐 이미지 OCR보다 정확도가 압도적으로 높아서 실사용의 주력 입력 경로다.
받은 문자를 그대로 복사해 붙여넣으면 일시·가맹점·금액을 뽑아낸다.

카드사마다 줄 순서와 마스킹 방식이 달라서, 파싱은 세 단계로 나눈다.

  1. 마스킹  — 금액이 아닌 숫자(카드번호·계좌번호·날짜·시각·마스킹된 이름)를 지운다
  2. 금액    — 남은 숫자 중에서 거래액을 고른다 (누적/잔액/승인번호는 제외)
  3. 가맹점  — 남은 글자 중에서 고른다 (사람 이름 줄은 버리고, 마지막 줄을 우선)

3번에서 '마지막 줄 우선'이 핵심이다. 국내 카드 문자는 거의 예외 없이
가맹점명이 마지막(또는 누적 금액 바로 위)에 온다. 예전처럼 '가장 긴 줄'을
고르면 '김철수님' 같은 실명 줄을 가맹점으로 잡는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

# --- 통화 -------------------------------------------------------------
UNIT_TO_CURRENCY = {
    "원": "KRW", "₩": "KRW", "krw": "KRW",
    "엔": "JPY", "¥": "JPY", "jpy": "JPY",
    "위안": "CNY", "cny": "CNY",
    "$": "USD", "usd": "USD",
    "€": "EUR", "eur": "EUR",
    "£": "GBP", "gbp": "GBP",
    "thb": "THB", "vnd": "VND", "sgd": "SGD", "hkd": "HKD",
    "twd": "TWD", "aud": "AUD", "cad": "CAD", "php": "PHP", "myr": "MYR",
}
# 국내 카드사는 해외 결제도 원화로 청구한다. 해외 승인 문자에 함께 오는
# 원화 금액은 '거래액'이 아니라 '청구액'이고, 둘의 비가 그 거래의 적용 환율이다.
BILLING_CURRENCY = "KRW"

_UNITS = r"원|엔|위안|₩|¥|\$|€|£|USD|KRW|JPY|EUR|GBP|CNY|THB|VND|SGD|HKD|TWD|AUD|CAD|PHP|MYR"
_NUMBER = r"(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?"

AMOUNT_PATTERN = re.compile(rf"(?<![\d.]){_NUMBER}\s*({_UNITS})?", re.I)
# '$12.34', 'USD 42.35' 처럼 통화 표기가 앞에 오는 경우.
# 단위 바로 앞에 숫자가 있으면 앞 금액의 접미 단위이므로 제외한다
# ('120,000원 3개월' 의 '원 3' 을 금액으로 잡으면 안 된다).
PREFIX_AMOUNT_PATTERN = re.compile(rf"(?<!\d)({_UNITS})\s*{_NUMBER}", re.I)

# --- 잡음 -------------------------------------------------------------
# 이 단어가 있는 줄의 금액은 거래액이 아니다.
NOISE_AMOUNT_HINTS = (
    "누적", "잔액", "합계", "총액", "한도", "포인트", "적립", "잔여", "가용",
    "승인번호", "거래번호", "이용가능", "캐시백", "마일리지", "할인금액",
)

# 가맹점명을 고를 때 지워야 하는 상용구.
NOISE_TOKENS = (
    "[web발신]", "(web발신)", "web발신", "[국외]", "[해외]", "해외승인", "국외승인",
    "해외이용", "승인취소", "부분취소", "매입취소", "결제취소", "정상승인", "승인",
    "결제완료", "결제", "일시불", "무이자", "개월", "할부", "체크카드", "신용카드",
    "선불카드", "체크", "신용", "누적", "매입", "출금", "입금", "이체", "사용",
    "알림", "정기결제", "자동이체", "페이머니", "카드",
)

REFUND_HINTS = ("취소", "환불", "반품", "refund", "cancel", "void")

# --- 정규식 -----------------------------------------------------------
# '신한카드(1234)', 'KB국민체크', '토스뱅크' 같은 발급사 표기
CARD_PATTERN = re.compile(
    r"([가-힣A-Za-z]{1,10}(?:카드|페이|은행|뱅크|체크|BC|비씨))\s*[\(\[]?(\d{2,4})?[\)\]]?"
)
# 카드사보다 먼저 잡아야 하는 간편결제 브랜드 (긴 것부터)
PAY_BRAND = re.compile(
    r"(?:(?<=\s)|^)(카카오페이머니|카카오페이|카카오뱅크|토스뱅크|토스페이|토스머니|"
    r"네이버페이|페이코|삼성페이|애플페이|제로페이|쓱페이|SSG페이|토스)(?=\s|$|[,.·|])"
)
CARD_NUMBER = re.compile(r"[\(\[]\s*\d{2,4}\s*[\)\]]")
# '352-****-4567', '8*3*', '****1234' 처럼 별표로 가린 번호
MASKED_NUMBER = re.compile(
    r"(?<![0-9A-Za-z가-힣])[0-9*\-]*\*+[0-9*\-]*(?![0-9A-Za-z가-힣])"
)
MASKED_NAME = re.compile(r"[가-힣]\*+[가-힣]")
# '김철수님' 처럼 사람 이름만 있는 줄
PERSON_NAME_LINE = re.compile(r"^[가-힣]{2,5}\s*님$")
TIME_PATTERN = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)(?::[0-5]\d)?\b")
DATE_PATTERNS = (
    re.compile(r"\b(20\d{2})[-./](\d{1,2})[-./](\d{1,2})\b"),
    re.compile(r"\b(\d{1,2})[/.-](\d{1,2})\b"),
    re.compile(r"(\d{1,2})월\s*(\d{1,2})일"),
)
INSTALLMENT_PATTERN = re.compile(r"(\d{1,2})\s*개월")


@dataclass
class ParsedTx:
    amount: Optional[int] = None          # 통화 최소단위
    currency: str = "KRW"
    merchant: str = ""
    day: Optional[date] = None
    time: str = ""
    card: str = ""
    is_refund: bool = False
    installment: str = ""                 # '3개월' 등, 일시불이면 빈 문자열
    converted_amount: Optional[int] = None   # 해외 결제 시 기준통화 청구액
    converted_currency: str = ""
    raw: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.amount is not None and self.amount != 0

    @property
    def implied_rate(self) -> Optional[float]:
        """카드사가 실제로 적용한 환율.

        해외 승인 문자에는 원통화 금액과 원화 청구액이 함께 온다. 이 둘의 비가
        곧 그 거래에 적용된 환율이라, 평균 환율보다 정확하다.
        """
        if not self.amount or not self.converted_amount:
            return None
        from .money import from_minor

        source = from_minor(abs(self.amount), self.currency)
        target = from_minor(abs(self.converted_amount), self.converted_currency)
        if source == 0:
            return None
        return float(Decimal(target) / Decimal(source))

    @property
    def note(self) -> str:
        """장부에 남길 출처 메모."""
        parts = [p for p in (self.card, self.time, self.installment) if p]
        return " ".join(parts)


# --- 마스킹 -----------------------------------------------------------

def _protected_spans(line: str) -> list[tuple[int, int]]:
    """통화 단위가 붙은 금액 구간. 날짜/시각 마스킹이 이걸 지우지 못하게 막는다.

    이 보호가 없으면 '$18.50' 이나 'USD 42.35' 가 날짜(18/50)로 잡혀 통째로
    지워진다.
    """
    spans = [(m.start(), m.end()) for m in PREFIX_AMOUNT_PATTERN.finditer(line)]
    spans += [(m.start(), m.end()) for m in AMOUNT_PATTERN.finditer(line) if m.group(3)]
    return spans


def _mask(line: str) -> str:
    """금액이 아닌 숫자를 같은 길이의 공백으로 바꾼다 (위치는 보존)."""
    protected = _protected_spans(line)

    def blank(match) -> str:
        if any(match.start() < end and start < match.end() for start, end in protected):
            return match.group(0)
        return " " * len(match.group(0))

    def blank_date(match) -> str:
        month, day = int(match.groups()[-2]), int(match.groups()[-1])
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return match.group(0)   # 12.34 같은 금액을 날짜로 오인하지 않는다
        return blank(match)

    text = PAY_BRAND.sub(blank, line)
    text = CARD_PATTERN.sub(blank, text)
    text = CARD_NUMBER.sub(blank, text)
    text = MASKED_NUMBER.sub(blank, text)
    text = MASKED_NAME.sub(blank, text)
    text = DATE_PATTERNS[0].sub(blank, text)
    for pattern in DATE_PATTERNS[1:]:
        text = pattern.sub(blank_date, text)
    text = TIME_PATTERN.sub(blank, text)
    return text


# --- 금액 -------------------------------------------------------------

@dataclass
class _Candidate:
    whole: str
    frac: Optional[str]
    unit: Optional[str]
    noisy: bool
    strong: bool          # 통화 단위나 천 단위 콤마가 붙어 있으면 금액이 거의 확실
    start: int
    end: int


def _iter_amounts(masked: str):
    """(start, end, whole, frac, unit). 통화 표기가 앞뒤 어디 있든 잡는다."""
    spans = []
    taken = []
    for m in PREFIX_AMOUNT_PATTERN.finditer(masked):
        spans.append((m.start(), m.end(), m.group(2), m.group(3), m.group(1)))
        taken.append((m.start(), m.end()))
    for m in AMOUNT_PATTERN.finditer(masked):
        if any(m.start() < end and start < m.end() for start, end in taken):
            continue
        spans.append((m.start(), m.end(), m.group(1), m.group(2), m.group(3)))
    spans.sort(key=lambda s: s[0])
    return spans


def _is_amount_like(whole: str, unit) -> bool:
    digits = whole.replace(",", "")
    if not (unit or "," in whole):
        # 단위도 콤마도 없으면 네 자리 이상일 때만 금액으로 본다
        if len(digits) < 4:
            return False
    return len(digits) <= 12


def _candidates(block: str) -> list[_Candidate]:
    found: list[_Candidate] = []
    for line in block.splitlines():
        noisy = any(hint in line for hint in NOISE_AMOUNT_HINTS)
        masked = _mask(line)
        for start, end, whole, frac, unit in _iter_amounts(masked):
            if not _is_amount_like(whole, unit):
                continue
            found.append(_Candidate(
                whole=whole, frac=frac, unit=unit, noisy=noisy,
                strong=bool(unit) or ("," in whole), start=start, end=end,
            ))
    return found


def _blank_amounts(masked: str) -> str:
    """금액으로 인정된 부분만 공백 처리. 가맹점명 속 숫자는 살린다.

    'GS25제주점'의 25, '스타벅스강남2호점'의 2가 지워지면 안 된다. 그래서
    통화 단위나 콤마가 붙은 것(strong)만 지우고, 그런 게 하나도 없는 줄에서만
    맨숫자를 금액으로 본다.
    """
    spans = [(s, e, w, u) for s, e, w, _f, u in _iter_amounts(masked)
             if _is_amount_like(w, u)]
    has_strong = any(bool(u) or "," in w for _s, _e, w, u in spans)
    out = list(masked)
    for start, end, whole, unit in spans:
        if has_strong and not (bool(unit) or "," in whole):
            continue
        for i in range(start, end):
            out[i] = " "
    return "".join(out)


def _to_minor(whole: str, frac: Optional[str], currency: str) -> int:
    from .money import minor_digits

    digits = minor_digits(currency)
    value = int(whole.replace(",", ""))
    if digits == 0:
        return value
    return value * (10 ** digits) + (int((frac + "00")[:digits]) if frac else 0)


def _currency_of(candidate: _Candidate) -> Optional[str]:
    if not candidate.unit:
        return None
    return UNIT_TO_CURRENCY.get(candidate.unit.lower())


_UNIT_NEAR_NUMBER = re.compile(rf"(?:\d\s*({_UNITS}))|(?:({_UNITS})\s*\d)", re.I)


def _detect_currency(text: str, fallback: str) -> str:
    """단위가 안 붙은 금액의 통화 추정. 숫자에 붙은 단위만 근거로 삼는다.

    블록 전체에서 '엔' 같은 글자를 찾으면 '엔진오일' 가맹점에서 오작동한다.
    """
    match = _UNIT_NEAR_NUMBER.search(text)
    if match:
        unit = match.group(1) or match.group(2)
        return UNIT_TO_CURRENCY.get(unit.lower(), fallback)
    return fallback


def _choose_amount(block: str, base_currency: str):
    """(거래액, 통화, 청구액, 청구통화, 경고들).

    해외 승인 문자에는 가맹점이 청구한 원통화 금액과, 카드사가 원화로 청구한
    금액이 함께 온다. 앞의 것이 거래액이고 뒤의 것은 환율 계산용이다.
    """
    warnings: list[str] = []
    found = _candidates(block)
    if not found:
        return (None, _detect_currency(block, base_currency), None, "",
                ["금액을 찾지 못했습니다"])

    pool = [c for c in found if c.strong and not c.noisy]
    if not pool:
        pool = [c for c in found if not c.noisy]
    if not pool:
        pool = found
        warnings.append("누적/잔액으로 보이는 금액만 있어 확실하지 않습니다")

    foreign = [c for c in pool if _currency_of(c) not in (None, BILLING_CURRENCY)]
    billed = next((c for c in pool if _currency_of(c) == BILLING_CURRENCY), None)

    if foreign and billed:
        picked, currency = foreign[0], _currency_of(foreign[0])
        converted = _to_minor(billed.whole, billed.frac, BILLING_CURRENCY)
        return (_to_minor(picked.whole, picked.frac, currency), currency,
                converted, BILLING_CURRENCY, warnings)

    picked = foreign[0] if foreign else pool[0]
    currency = _currency_of(picked) or _detect_currency(block, base_currency)
    distinct = {(c.whole, c.frac) for c in pool}
    if len(distinct) > 1:
        warnings.append(
            "금액 후보가 여러 개입니다: " + ", ".join(sorted(w for w, _ in distinct)[:4])
        )
    return _to_minor(picked.whole, picked.frac, currency), currency, None, "", warnings


# --- 날짜 / 가맹점 ----------------------------------------------------

def _pick_date(block: str, default_year: Optional[int]) -> Optional[date]:
    year = default_year or date.today().year
    for line in block.splitlines():
        m = DATE_PATTERNS[0].search(line)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                continue
    for pattern in DATE_PATTERNS[1:]:
        for line in block.splitlines():
            for m in pattern.finditer(line):
                try:
                    return date(year, int(m.group(1)), int(m.group(2)))
                except ValueError:
                    continue
    return None


def _clean_merchant_line(line: str) -> str:
    text = _blank_amounts(_mask(line))
    lowered = text.lower()
    for token in NOISE_TOKENS:
        index = lowered.find(token)
        while index >= 0:
            text = text[:index] + " " * len(token) + text[index + len(token):]
            lowered = text.lower()
            index = lowered.find(token)
    text = re.sub(r"[\[\]()<>·|,:/\\]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _looks_like_merchant(cleaned: str, original: str) -> bool:
    if len(cleaned) < 2:
        return False
    if cleaned.replace(" ", "").isdigit():
        return False
    if PERSON_NAME_LINE.match(original.strip()):
        return False        # '김철수님' 같은 실명 줄
    if PERSON_NAME_LINE.match(cleaned):
        return False
    if not re.search(r"[0-9A-Za-z가-힣]", cleaned):
        return False
    return True


def _pick_merchant(block: str) -> str:
    """가맹점명은 마지막에 온다. 뒤에서부터 첫 번째로 그럴듯한 줄을 고른다."""
    picks: list[str] = []
    for line in block.splitlines():
        if any(hint in line for hint in NOISE_AMOUNT_HINTS):
            continue
        cleaned = _clean_merchant_line(line)
        if _looks_like_merchant(cleaned, line):
            picks.append(cleaned)
    return picks[-1] if picks else ""


# --- 블록 분리 --------------------------------------------------------

def _split_blocks(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    # 1) [Web발신] 승인 문자 여러 건. 줄 경계에서만 자른다.
    if normalized.lower().count("web발신") > 1:
        parts = re.split(r"\n(?=\[?\s*[Ww]eb발신)", normalized)
        return [p.strip() for p in parts if p.strip()]
    # 2) 빈 줄로 구분된 블록
    if "\n\n" in normalized:
        return [b.strip() for b in re.split(r"\n\s*\n", normalized) if b.strip()]
    lines = [l for l in normalized.split("\n") if l.strip()]
    # 3) 줄마다 금액이 있으면 한 줄 = 한 건 (은행/카드 앱 거래내역 목록)
    with_amount = [l for l in lines if re.search(rf"\d[\d,]*\s*({_UNITS})", l, re.I)]
    if len(lines) > 1 and len(with_amount) >= max(2, len(lines) - 1):
        return lines
    return ["\n".join(lines)]


# --- 진입점 -----------------------------------------------------------

def parse_block(block: str, default_year: Optional[int] = None,
                base_currency: str = "KRW") -> ParsedTx:
    base = (base_currency or "KRW").upper()
    amount, currency, converted, billed_currency, warnings = _choose_amount(block, base)
    is_refund = any(hint in block.lower() for hint in REFUND_HINTS)

    brand = PAY_BRAND.search(block)
    card_match = CARD_PATTERN.search(block)
    time_match = TIME_PATTERN.search(block)
    installment = INSTALLMENT_PATTERN.search(block)

    tx = ParsedTx(
        amount=(-amount if (amount is not None and is_refund) else amount),
        currency=currency,
        merchant=_pick_merchant(block),
        day=_pick_date(block, default_year),
        time=(time_match.group(0) if time_match else ""),
        card=(brand.group(1) if brand else (card_match.group(1) if card_match else "")),
        is_refund=is_refund,
        installment=(installment.group(0).replace(" ", "") if installment else ""),
        converted_amount=(-converted if (converted and is_refund) else converted),
        converted_currency=billed_currency,
        raw=block.strip(),
        warnings=list(warnings),
    )
    if not tx.merchant:
        tx.warnings.append("가맹점명을 찾지 못했습니다")
    if tx.day is None:
        tx.warnings.append("날짜를 찾지 못했습니다")
    return tx


def parse_text(text: str, default_year: Optional[int] = None,
               base_currency: str = "KRW") -> list[ParsedTx]:
    """붙여넣은 텍스트에서 거래 여러 건을 뽑는다."""
    return [parse_block(block, default_year, base_currency)
            for block in _split_blocks(text)]
