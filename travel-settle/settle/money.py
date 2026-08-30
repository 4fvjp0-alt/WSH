"""금액 연산.

정산에서 1원이 새는 대부분의 원인은 부동소수점이다. 이 모듈은 모든 금액을
`최소 단위 정수`(KRW는 원, USD는 센트)로만 다루고, 분배는 유리수(Fraction)로
정확히 계산한 뒤 최대잔여법으로 정수에 떨어뜨린다. 따라서 분배 결과의 합은
언제나 원본 총액과 **정확히** 일치한다.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Iterable, Sequence

# 통화별 소수 자릿수. 없으면 2로 본다.
MINOR_DIGITS = {
    "KRW": 0, "JPY": 0, "VND": 0, "IDR": 0, "CLP": 0, "HUF": 0, "TWD": 0,
    "USD": 2, "EUR": 2, "GBP": 2, "CNY": 2, "THB": 2, "SGD": 2, "HKD": 2,
    "AUD": 2, "CAD": 2, "CHF": 2, "PHP": 2, "MYR": 2, "NZD": 2, "TRY": 2,
}

SYMBOL_SUFFIX = {"KRW": "원", "JPY": "엔"}
SYMBOL_PREFIX = {"USD": "$", "EUR": "€", "GBP": "£", "CNY": "¥"}


def minor_digits(currency: str) -> int:
    return MINOR_DIGITS.get(currency.upper(), 2)


def minor_scale(currency: str) -> int:
    return 10 ** minor_digits(currency)


def to_minor(value, currency: str) -> int:
    """사람이 입력한 금액('12,500', 12500, Decimal('12.34'))을 최소단위 정수로."""
    if isinstance(value, int):
        return value * minor_scale(currency)
    if isinstance(value, float):
        dec = Decimal(str(value))
    elif isinstance(value, Decimal):
        dec = value
    else:
        text = str(value).strip().replace(",", "").replace("_", "")
        for junk in ("원", "엔", "₩", "$", "€", "£", "¥"):
            text = text.replace(junk, "")
        text = text.strip()
        if not text:
            raise ValueError("금액이 비어 있습니다")
        try:
            dec = Decimal(text)
        except InvalidOperation as exc:
            raise ValueError(f"금액을 해석할 수 없습니다: {value!r}") from exc
    scaled = dec * minor_scale(currency)
    rounded = int(scaled.to_integral_value(rounding="ROUND_HALF_UP"))
    return rounded


def from_minor(amount: int, currency: str) -> Decimal:
    digits = minor_digits(currency)
    if digits == 0:
        return Decimal(amount)
    return Decimal(amount).scaleb(-digits)


def format_money(amount: int, currency: str = "KRW", with_currency: bool = True) -> str:
    """'12,500원', '-$12.34' 형태로 표시."""
    digits = minor_digits(currency)
    sign = "-" if amount < 0 else ""
    value = abs(amount)
    if digits == 0:
        body = f"{value:,}"
    else:
        whole, frac = divmod(value, 10 ** digits)
        body = f"{whole:,}.{frac:0{digits}d}"
    if not with_currency:
        return sign + body
    cur = currency.upper()
    if cur in SYMBOL_SUFFIX:
        return f"{sign}{body}{SYMBOL_SUFFIX[cur]}"
    if cur in SYMBOL_PREFIX:
        return f"{sign}{SYMBOL_PREFIX[cur]}{body}"
    return f"{sign}{body} {cur}"


def _as_fraction(value) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(Decimal(str(value)))
    if isinstance(value, Decimal):
        return Fraction(value)
    return Fraction(Decimal(str(value)))


def allocate(total: int, weights: Sequence, seed: int = 0) -> list[int]:
    """`total`을 `weights` 비율로 나눈 정수 목록. 합계는 total과 정확히 일치한다.

    최대잔여법(largest remainder)으로 나머지를 배분하되, 동률일 때의 우선순위를
    `seed`로 회전시킨다. 매번 같은 사람이 1원을 더 부담하는 일을 막기 위함이다.
    """
    n = len(weights)
    if n == 0:
        if total != 0:
            raise ValueError("분배 대상이 없는데 금액이 남았습니다")
        return []
    fw = [_as_fraction(w) for w in weights]
    if any(w < 0 for w in fw):
        raise ValueError("가중치는 음수일 수 없습니다")
    total_weight = sum(fw, Fraction(0))
    if total_weight == 0:
        raise ValueError("가중치 합이 0입니다")

    sign = -1 if total < 0 else 1
    magnitude = abs(total)
    exact = [Fraction(magnitude) * w / total_weight for w in fw]
    base = [int(e) for e in exact]  # 음수가 아니므로 int()는 floor
    remainder = magnitude - sum(base)
    order = sorted(
        range(n),
        key=lambda i: (-(exact[i] - base[i]), (i - seed) % n),
    )
    for k in range(remainder):
        base[order[k]] += 1
    return [sign * b for b in base]


def allocate_exact(total: int, values: Sequence[int]) -> list[int]:
    """이미 확정된 금액 목록을 검증한다. 합계가 총액과 다르면 오류."""
    got = sum(values)
    if got != total:
        raise ValueError(f"지정 금액 합계({got})가 총액({total})과 다릅니다")
    return list(values)


def round_to_unit(amount: int, unit: int) -> int:
    """`unit` 배수로 반올림 (0에서 먼 쪽으로 절반 올림)."""
    if unit <= 1:
        return amount
    sign = -1 if amount < 0 else 1
    value = abs(amount)
    quotient, rest = divmod(value, unit)
    if rest * 2 >= unit:
        quotient += 1
    return sign * quotient * unit


def round_preserving_sum(values: Sequence[int], unit: int) -> list[int]:
    """각 값을 `unit` 배수로 반올림하되 전체 합은 그대로 유지한다.

    잔액(net) 목록의 합은 0이어야 하는데, 개별 반올림만 하면 합이 깨진다.
    반올림 오차가 큰 순서대로 한 칸씩 되돌려 합을 맞춘다.
    """
    if unit <= 1:
        return list(values)
    original_sum = sum(values)
    if original_sum % unit != 0:
        raise ValueError("합계가 반올림 단위의 배수가 아니어서 유지할 수 없습니다")
    rounded = [round_to_unit(v, unit) for v in values]
    drift = sum(rounded) - original_sum
    steps, rest = divmod(abs(drift), unit)
    if rest != 0:  # pragma: no cover - 반올림 결과는 항상 unit 배수
        raise AssertionError("반올림 오차가 단위의 배수가 아닙니다")
    if steps:
        direction = -unit if drift > 0 else unit
        # 되돌렸을 때 원래 값과의 오차가 가장 적게 커지는 항목부터 조정
        order = sorted(
            range(len(values)),
            key=lambda i: (abs(rounded[i] + direction - values[i]), i),
        )
        for k in range(steps):
            rounded[order[k % len(order)]] += direction
    return rounded


def convert(amount_minor: int, src: str, dst: str, rate) -> int:
    """`src` 통화 최소단위 금액을 `dst` 통화 최소단위 금액으로 환산.

    rate는 "src 1단위 = rate dst단위" 의미의 사람이 읽는 환율
    (예: JPY→KRW 라면 rate=9.1 은 1엔 = 9.1원).
    """
    if src.upper() == dst.upper():
        return amount_minor
    if rate is None:
        raise ValueError(f"{src}->{dst} 환율이 없습니다")
    value = Fraction(amount_minor, minor_scale(src)) * _as_fraction(rate)
    scaled = value * minor_scale(dst)
    # 반올림 (0.5는 0에서 먼 쪽)
    num, den = scaled.numerator, scaled.denominator
    sign = -1 if num < 0 else 1
    num = abs(num)
    quotient, rest = divmod(num, den)
    if rest * 2 >= den:
        quotient += 1
    return sign * quotient


def sum_minor(values: Iterable[int]) -> int:
    return sum(values)
