"""결제내역 캡쳐 이미지 → 거래내역 추출.

별도 OCR API 키를 쓰지 않고, 사용자가 이미 쓰는 Claude Code CLI(`claude`)를
그대로 호출한다. 구독 플랜 안에서 동작하고 이미지를 외부 OCR 서비스로
보내지 않는다.

추출 결과는 절대 자동 확정하지 않는다. 반드시 사람이 확인하는 검토 단계를
거쳐 장부에 들어간다.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional

from .money import to_minor
from .parse_text import ParsedTx

ENV_CMD = "TRAVEL_SETTLE_CLAUDE_CMD"     # 기본 'claude'
ENV_MOCK = "TRAVEL_SETTLE_OCR_MOCK"      # 테스트용: 응답 JSON 파일 경로
ENV_TIMEOUT = "TRAVEL_SETTLE_OCR_TIMEOUT"

SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".heic"}

PROMPT_TEMPLATE = """\
아래 경로의 이미지는 결제 내역 또는 영수증 캡쳐입니다.

경로: {path}

Read 도구로 이 이미지를 읽고, 보이는 결제 건을 모두 추출해서 JSON만 출력하세요.

출력 스키마:
{{"transactions": [
  {{"date": "YYYY-MM-DD" 또는 null,
    "time": "HH:MM" 또는 null,
    "merchant": "가맹점명",
    "amount": 숫자,
    "currency": "KRW",
    "is_refund": false,
    "note": "불확실한 점이 있으면 여기에",
    "confidence": 0.0~1.0}}
]}}

규칙:
- amount 는 통화의 기본 단위로 적습니다. KRW/JPY 는 정수, USD/EUR 는 소수점 둘째 자리까지.
- 누적 사용액, 잔액, 한도, 포인트, 적립은 거래가 아니므로 제외합니다.
- 승인취소/환불 건은 is_refund 를 true 로 하고 amount 는 양수로 둡니다.
- 날짜에 연도가 없으면 {year} 년으로 봅니다.
- 글자가 흐리거나 가려져 확신이 없으면 confidence 를 낮추고 note 에 이유를 적습니다.
- JSON 외의 설명, 인사말, 코드펜스는 출력하지 마세요.
"""


class OcrError(Exception):
    """이미지에서 거래내역을 뽑지 못했을 때."""


def claude_command() -> list[str]:
    raw = os.environ.get(ENV_CMD, "claude")
    return shlex.split(raw)


def is_available() -> bool:
    if os.environ.get(ENV_MOCK):
        return True
    from shutil import which

    command = claude_command()
    return bool(command) and which(command[0]) is not None


def _extract_json(text: str) -> dict:
    text = text.strip()
    if not text:
        raise OcrError("Claude CLI 응답이 비어 있습니다")
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise OcrError(f"응답을 JSON으로 해석하지 못했습니다: {exc}") from exc
    raise OcrError("응답에서 JSON을 찾지 못했습니다")


def _run_claude(prompt: str, timeout: int) -> str:
    command = claude_command() + [
        "-p", prompt,
        "--output-format", "json",
        "--allowedTools", "Read",
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False,
        )
    except FileNotFoundError as exc:
        raise OcrError(
            f"'{command[0]}' 명령을 찾을 수 없습니다. Claude Code CLI를 설치했는지 확인하세요. "
            f"다른 실행 경로를 쓰려면 {ENV_CMD} 환경변수를 설정하세요."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise OcrError(f"Claude CLI 응답이 {timeout}초 안에 오지 않았습니다") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[:500]
        raise OcrError(f"Claude CLI 실행 실패 (코드 {completed.returncode}): {detail}")

    output = completed.stdout.strip()
    # --output-format json 은 봉투(envelope)로 감싸서 준다
    try:
        envelope = json.loads(output)
        if isinstance(envelope, dict) and "result" in envelope:
            return str(envelope["result"])
    except json.JSONDecodeError:
        pass
    return output


def _to_parsed(entry: dict, default_year: int, image_path: str) -> ParsedTx:
    currency = str(entry.get("currency") or "KRW").upper()
    warnings: list[str] = []
    amount_raw = entry.get("amount")
    amount: Optional[int]
    if amount_raw is None:
        amount = None
        warnings.append("금액을 읽지 못했습니다")
    else:
        try:
            amount = to_minor(amount_raw, currency)
        except ValueError as exc:
            amount = None
            warnings.append(str(exc))

    day = None
    raw_date = entry.get("date")
    if raw_date:
        try:
            day = date.fromisoformat(str(raw_date)[:10])
        except ValueError:
            warnings.append(f"날짜 형식을 알 수 없습니다: {raw_date}")
    else:
        warnings.append("날짜를 찾지 못했습니다")

    is_refund = bool(entry.get("is_refund"))
    if amount is not None and is_refund:
        amount = -abs(amount)

    confidence = entry.get("confidence")
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = None
    if confidence is not None and confidence < 0.7:
        warnings.append(f"인식 신뢰도 낮음 ({confidence:.0%}) — 반드시 확인하세요")
    note = str(entry.get("note") or "").strip()
    if note:
        warnings.append(note)

    return ParsedTx(
        amount=amount, currency=currency,
        merchant=str(entry.get("merchant") or "").strip(),
        day=day, time=str(entry.get("time") or ""),
        card="", is_refund=is_refund,
        raw=f"[이미지] {image_path}", warnings=warnings,
    )


def extract(image_path: str | Path, default_year: int | None = None, timeout: int | None = None) -> list[ParsedTx]:
    """캡쳐 이미지에서 거래내역 후보를 뽑는다. 확정은 호출자(검토 단계)의 몫."""
    path = Path(image_path).expanduser().resolve()
    if not path.exists():
        raise OcrError(f"이미지를 찾을 수 없습니다: {path}")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise OcrError(
            f"지원하지 않는 이미지 형식입니다: {path.suffix} "
            f"(지원: {', '.join(sorted(SUPPORTED_SUFFIXES))})"
        )
    year = default_year or date.today().year
    timeout = timeout or int(os.environ.get(ENV_TIMEOUT, "180"))

    mock = os.environ.get(ENV_MOCK)
    if mock:
        raw_text = Path(mock).read_text(encoding="utf-8")
    else:
        raw_text = _run_claude(
            PROMPT_TEMPLATE.format(path=str(path), year=year), timeout
        )

    payload = _extract_json(raw_text)
    entries = payload.get("transactions")
    if entries is None and isinstance(payload, dict) and "amount" in payload:
        entries = [payload]
    if not isinstance(entries, list):
        raise OcrError("응답에 transactions 배열이 없습니다")
    if not entries:
        raise OcrError("이미지에서 거래내역을 찾지 못했습니다")
    return [_to_parsed(e, year, str(path)) for e in entries if isinstance(e, dict)]
