"""카드 승인 문자·간편결제 알림·거래내역 목록 텍스트 파서.

캡쳐 이미지 OCR보다 정확도가 압도적으로 높아서 실사용의 주력 입력 경로다.
문자를 그대로 복사해 붙여넣으면 일시·가맹점·금액을 뽑아낸다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

CURRENCY_TOKENS = [
    ("KRW", ("원", "₩", "krw", "won")),
    ("JPY", ("엔", "¥", "jpy", "yen")),
    ("USD", ("$", "usd", "달러")),
    ("EUR", ("€", "eur", "유로")),
    ("THB", ("thb", "바트", "฿")),
    ("VND", ("vnd", "동")),
]

# 금액이지만 거래액이 아닌 줄
NOISE_AMOUNT_HINTS = ("누적", "잔액", "합계", "총액", "한도", "포인트", "적립", "잔여", "가용")

REFUND_HINTS = ("취소", "환불", "반품", "refund", "cancel")

CARD_PATTERN = re.compile(
    r"([가-힣A-Za-z]{2,10}(?:카드|페이|은행|체크|BC|비씨))\s*[\(\[]?(\d{2,4})?[\)\]]?"
)
AMOUNT_PATTERN = re.compile(
    r"(?<![\d.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?\s*"
    r"(원|엔|₩|¥|\$|€|USD|KRW|JPY|EUR|THB|VND)?", re.I)
# '$12.34', 'USD 42.35' 처럼 통화 기호가 앞에 오는 표기
PREFIX_AMOUNT_PATTERN = re.compile(
    r"(₩|¥|\$|€|USD|KRW|JPY|EUR|THB|VND)\s*(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?", re.I)
TIME_PATTERN = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)(?::[0-5]\d)?\b")
DATE_PATTERNS = [
    re.compile(r"\b(20\d{2})[-./](\d{1,2})[-./](\d{1,2})\b"),
    re.compile(r"\b(\d{1,2})[/.](\d{1,2})\b"),
    re.compile(r"(\d{1,2})월\s*(\d{1,2})일"),
]
MASKED_NAME = re.compile(r"[가-힣]\*+[가-힣]")
NOISE_TOKENS = [
    "[web발신]", "(web발신)", "web발신", "[국외]", "[해외]", "승인취소", "승인", "결제취소",
    "결제완료", "결제", "일시불", "체크", "누적", "체크카드", "신용", "할부", "개월",
    "정상승인", "매입", "출금", "입금", "사용", "알림",
]


@dataclass
class ParsedTx:
    amount: Optional[int] = None          # 통화 최소단위
    currency: str = "KRW"
    merchant: str = ""
    day: Optional[date] = None
    time: str = ""
    card: str = ""
    is_refund: bool = False
    raw: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.amount is not None and self.amount != 0


UNIT_TO_CURRENCY = {
    "원": "KRW", "₩": "KRW", "krw": "KRW",
    "엔": "JPY", "¥": "JPY", "jpy": "JPY",
    "$": "USD", "usd": "USD",
    "€": "EUR", "eur": "EUR",
    "thb": "THB", "vnd": "VND",
}

CARD_NUMBER = re.compile(r"[\(\[]\s*\d{2,4}\s*[\)\]]")


def _detect_currency(text: str) -> str:
    lowered = text.lower()
    for code, tokens in CURRENCY_TOKENS:
        for token in tokens:
            if token in lowered:
                return code
    return "KRW"


def _blank(match) -> str:
    return " " * len(match.group(0))


def _protected_spans(line: str) -> list[tuple[int, int]]:
    """통화 단위가 붙은 금액 구간. 날짜/시각 마스킹이 이걸 지우지 못하게 막는다.

    이 보호가 없으면 '$18.50' 이나 'USD 42.35' 가 날짜 패턴(18/50)으로
    잡혀 통째로 지워진다.
    """
    spans = [(m.start(), m.end()) for m in PREFIX_AMOUNT_PATTERN.finditer(line)]
    for m in AMOUNT_PATTERN.finditer(line):
        if m.group(3):
            spans.append((m.start(), m.end()))
    return spans


def _mask(line: str) -> str:
    """금액이 아닌 숫자(카드번호·날짜·시각·마스킹된 이름)를 공백으로 지운다.

    이 단계를 먼저 하지 않으면 카드번호 (1234) 가 금액 1,234원으로,
    가맹점 '스타벅스강남2호점'의 2가 금액으로 잡힌다.
    """
    protected = _protected_spans(line)

    def replace(match) -> str:
        if any(match.start() < end and start < match.end() for start, end in protected):
            return match.group(0)
        return " " * len(match.group(0))

    def replace_date(match) -> str:
        groups = match.groups()
        month, day = int(groups[-2]), int(groups[-1])
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return match.group(0)
        return replace(match)

    text = CARD_PATTERN.sub(replace, line)
    text = CARD_NUMBER.sub(replace, text)
    text = DATE_PATTERNS[0].sub(replace, text)
    for pattern in DATE_PATTERNS[1:]:
        text = pattern.sub(replace_date, text)
    text = TIME_PATTERN.sub(replace, text)
    text = MASKED_NAME.sub(replace, text)
    return text


@dataclass
class _Candidate:
    whole: str
    frac: Optional[str]
    unit: Optional[str]
    noisy: bool
    strong: bool   # 통화 단위나 천 단위 콤마가 붙어 있으면 금액이 거의 확실


def _iter_amounts(masked: str):
    """(start, end, whole, frac, unit) 목록. 접두/접미 통화 표기를 모두 지원."""
    spans: list[tuple[int, int, str, str, str]] = []
    taken: list[tuple[int, int]] = []
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
    strong = bool(unit) or ("," in whole)
    if not strong and len(digits) < 4:
        return False
    return len(digits) <= 12


def _candidates(block: str) -> list[_Candidate]:
    found: list[_Candidate] = []
    for line in block.splitlines():
        noisy = any(hint in line for hint in NOISE_AMOUNT_HINTS)
        masked = _mask(line)
        for _, _, whole, frac, unit in _iter_amounts(masked):
            if not _is_amount_like(whole, unit):
                continue
            strong = bool(unit) or ("," in whole)
            found.append(_Candidate(whole, frac, unit, noisy, strong))
    return found


def _blank_amounts(masked: str) -> str:
    """금액으로 인정된 부분만 공백 처리. 가맹점명 속 숫자는 살린다."""
    out = list(masked)
    for start, end, whole, _frac, unit in _iter_amounts(masked):
        if _is_amount_like(whole, unit):
            for i in range(start, end):
                out[i] = " "
    return "".join(out)


def _to_minor(whole: str, frac: Optional[str], currency: str) -> int:
    from .money import minor_digits

    digits = minor_digits(currency)
    value = int(whole.replace(",", ""))
    if digits == 0:
        return value
    cents = 0
    if frac:
        cents = int((frac + "00")[:digits])
    return value * (10 ** digits) + cents


def _choose_amount(block: str) -> tuple[Optional[int], str, list[str]]:
    warnings: list[str] = []
    found = _candidates(block)
    if not found:
        return None, _detect_currency(block), ["금액을 찾지 못했습니다"]
    pool = [c for c in found if c.strong and not c.noisy]
    if not pool:
        pool = [c for c in found if not c.noisy]
    if not pool:
        pool = found
        warnings.append("누적/잔액으로 보이는 금액만 있어 확실하지 않습니다")
    if len(pool) > 1 and len({(c.whole, c.frac) for c in pool}) > 1:
        warnings.append(
            "금액 후보가 여러 개입니다: " + ", ".join(c.whole for c in pool[:4])
        )
    pick = pool[0]
    unit = (pick.unit or "").lower()
    currency = UNIT_TO_CURRENCY.get(unit) or _detect_currency(block)
    return _to_minor(pick.whole, pick.frac, currency), currency, warnings


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
            m = pattern.search(line)
            if m:
                try:
                    return date(year, int(m.group(1)), int(m.group(2)))
                except ValueError:
                    continue
    return None


def _clean_merchant_line(line: str) -> str:
    text = _blank_amounts(_mask(line))
    lowered = text.lower()
    for token in NOISE_TOKENS:
        idx = lowered.find(token)
        while idx >= 0:
            text = text[:idx] + " " * len(token) + text[idx + len(token):]
            lowered = text.lower()
            idx = lowered.find(token)
    text = re.sub(r"[\[\]()<>·|,:/\\]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _pick_merchant(block: str) -> str:
    best = ""
    for line in block.splitlines():
        if any(hint in line for hint in NOISE_AMOUNT_HINTS):
            continue
        cleaned = _clean_merchant_line(line)
        if len(cleaned) < 2 or cleaned.replace(" ", "").isdigit():
            continue
        if len(cleaned) > len(best):
            best = cleaned
    return best


def _split_blocks(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    # 1) [Web발신] 로 시작하는 승인 문자 여러 건
    if normalized.lower().count("web발신") > 1:
        # 줄 경계에서만 자른다. 문자 중간에서 자르면 '[' 하나짜리 빈 블록이 생긴다.
        parts = re.split(r"\n(?=\[?\s*[Ww]eb발신)", normalized)
        return [p.strip() for p in parts if p.strip()]
    # 2) 빈 줄로 구분된 블록
    if "\n\n" in normalized:
        return [b.strip() for b in re.split(r"\n\s*\n", normalized) if b.strip()]
    lines = [l for l in normalized.split("\n") if l.strip()]
    # 3) 줄마다 금액이 있으면 한 줄 = 한 건 (은행/카드앱 거래내역 목록)
    with_amount = [l for l in lines if re.search(r"\d[\d,]*\s*(원|엔|\$|¥|€)", l)]
    if len(lines) > 1 and len(with_amount) >= max(2, len(lines) - 1):
        return lines
    return ["\n".join(lines)]


def parse_block(block: str, default_year: Optional[int] = None) -> ParsedTx:
    amount, currency, warnings = _choose_amount(block)
    is_refund = any(hint in block.lower() for hint in REFUND_HINTS)
    card_match = CARD_PATTERN.search(block)
    time_match = TIME_PATTERN.search(_mask(block) if False else block)
    tx = ParsedTx(
        amount=(-amount if (amount is not None and is_refund) else amount),
        currency=currency,
        merchant=_pick_merchant(block),
        day=_pick_date(block, default_year),
        time=(time_match.group(0) if time_match else ""),
        card=(card_match.group(1) if card_match else ""),
        is_refund=is_refund,
        raw=block.strip(),
        warnings=list(warnings),
    )
    if not tx.merchant:
        tx.warnings.append("가맹점명을 찾지 못했습니다")
    if tx.day is None:
        tx.warnings.append("날짜를 찾지 못했습니다")
    return tx


def parse_text(text: str, default_year: Optional[int] = None) -> list[ParsedTx]:
    """붙여넣은 텍스트에서 거래 여러 건을 뽑는다."""
    return [parse_block(block, default_year) for block in _split_blocks(text)]
