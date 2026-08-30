"""터미널 출력 도우미. 한글 폭(2칸)을 고려해 표를 정렬한다."""

from __future__ import annotations

import unicodedata
from typing import Iterable, Sequence


def width(text: str) -> int:
    total = 0
    for ch in str(text):
        total += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return total


def pad(text: str, size: int, align: str = "left") -> str:
    text = str(text)
    space = max(0, size - width(text))
    if align == "right":
        return " " * space + text
    if align == "center":
        left = space // 2
        return " " * left + text + " " * (space - left)
    return text + " " * space


def truncate(text: str, size: int) -> str:
    text = str(text)
    if width(text) <= size:
        return text
    out = ""
    used = 0
    for ch in text:
        w = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if used + w > size - 1:
            break
        out += ch
        used += w
    return out + "…"


def table(
    headers: Sequence[str],
    rows: Iterable[Sequence[str]],
    aligns: Sequence[str] | None = None,
    indent: str = "  ",
) -> str:
    rows = [[str(c) for c in row] for row in rows]
    columns = len(headers)
    aligns = list(aligns or ["left"] * columns)
    sizes = [width(h) for h in headers]
    for row in rows:
        for i in range(columns):
            sizes[i] = max(sizes[i], width(row[i]) if i < len(row) else 0)
    lines = [
        indent + "  ".join(pad(h, sizes[i], "center" if aligns[i] == "center" else aligns[i])
                           for i, h in enumerate(headers)),
        indent + "  ".join("─" * sizes[i] for i in range(columns)),
    ]
    for row in rows:
        cells = []
        for i in range(columns):
            value = row[i] if i < len(row) else ""
            cells.append(pad(value, sizes[i], aligns[i]))
        lines.append(indent + "  ".join(cells).rstrip())
    return "\n".join(lines)


def bar(value: int, total: int, size: int = 20) -> str:
    if total <= 0:
        return " " * size
    filled = round(size * min(1.0, abs(value) / abs(total)))
    return "█" * filled + "·" * (size - filled)


def rule(title: str = "", size: int = 66) -> str:
    if not title:
        return "─" * size
    head = f"── {title} "
    return head + "─" * max(0, size - width(head))


def heading(title: str, size: int = 66) -> str:
    line = "═" * size
    return f"{line}\n  {title}\n{line}"
