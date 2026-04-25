from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup

_DATE_TOKEN_RE = re.compile(
    r"""
    [12]\d{3}[年./-]\d{1,2}(?:月|[./-])\d{1,2}(?:日)?
    (?:\s+\d{1,2}:\d{2}(?::\d{2})?)?
    |
    (?:Jan|January|Feb|February|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|August|Sep|Sept|September|Oct|October|Nov|November|Dec|December)
    \s+\d{1,2},\s+[12]\d{3}
    (?:\s+\d{1,2}:\d{2}(?::\d{2})?)?
    |
    \d{1,2}[./-]\d{1,2}
    """,
    re.VERBOSE,
)
_PUBLISHED_AT_HINTS = (
    "发布时间",
    "发布日期",
    "日期",
    "时间",
    "发布于",
    "发表于",
    "更新于",
)
_META_PUBLISHED_AT_KEYS = {
    "article:published_time",
    "article:published",
    "og:published_time",
    "publishdate",
    "pubdate",
    "datepublished",
    "weibo:article:create_at",
}
_STRUCTURED_DATE_CLASSES = {
    "aside-time",
    "times",
    "u-date",
    "u-time",
}


def parse_datetime_text(
    value: str | None,
    *,
    default_year: int | None = None,
) -> datetime | None:
    if not value:
        return None

    text = re.sub(r"\s+", " ", value).strip()
    if not text:
        return None

    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y.%m.%d %H:%M:%S",
        "%Y.%m.%d %H:%M",
        "%Y年%m月%d日 %H:%M:%S",
        "%Y年%m月%d日 %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
        "%Y年%m月%d日",
        "%B %d, %Y %H:%M:%S",
        "%B %d, %Y %H:%M",
        "%b %d, %Y %H:%M:%S",
        "%b %d, %Y %H:%M",
        "%B %d, %Y",
        "%b %d, %Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    split_with_year_patterns = (
        re.fullmatch(r"(\d{1,2})\s+([12]\d{3})[./-](\d{1,2})", text),
        re.fullmatch(r"([12]\d{3})[./-](\d{1,2})\s+(\d{1,2})", text),
    )
    for match in split_with_year_patterns:
        if not match:
            continue
        try:
            if len(match.groups()) == 3 and len(match.group(1)) <= 2:
                return datetime(int(match.group(2)), int(match.group(3)), int(match.group(1)))
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            continue

    if default_year is not None:
        if match := re.fullmatch(r"(\d{1,2})\s+(\d{1,2})", text):
            first = int(match.group(1))
            second = int(match.group(2))
            try:
                if first > 12 >= second:
                    return datetime(default_year, second, first)
                if second > 12 >= first:
                    return datetime(default_year, first, second)
            except ValueError:
                pass

        for fmt in ("%m-%d", "%m/%d", "%m.%d"):
            try:
                partial = datetime.strptime(text, fmt)
                return partial.replace(year=default_year)
            except ValueError:
                continue

    return None


def extract_datetime_from_text(
    text: str | None,
    *,
    default_year: int | None = None,
    require_hint: bool = False,
) -> datetime | None:
    if not text:
        return None

    normalized = re.sub(r"\r\n?", "\n", text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in normalized.split("\n")]
    lines = [line for line in lines if line]

    def _find_in_lines(candidates: list[str]) -> datetime | None:
        for line in candidates:
            for match in _DATE_TOKEN_RE.finditer(line):
                parsed = parse_datetime_text(match.group(0), default_year=default_year)
                if parsed is not None:
                    return parsed
        return None

    hinted_indices = [
        index
        for index, line in enumerate(lines)
        if any(hint in line for hint in _PUBLISHED_AT_HINTS)
    ]
    if hinted_indices:
        parsed = _find_in_lines([lines[index] for index in hinted_indices])
        if parsed is not None:
            return parsed

        contextual_candidates: list[str] = []
        for index in hinted_indices:
            contextual_candidates.append(" ".join(lines[index : index + 2]))
            contextual_candidates.append(" ".join(lines[index : index + 3]))
            if index > 0:
                contextual_candidates.append(" ".join(lines[index - 1 : index + 2]))
        parsed = _find_in_lines(contextual_candidates)
        if parsed is not None:
            return parsed

    if require_hint:
        return None

    return _find_in_lines(lines)


def extract_datetime_from_html(
    html: str | None,
    *,
    default_year: int | None = None,
    require_hint: bool = False,
) -> datetime | None:
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")

    for meta in soup.find_all("meta"):
        for attr in ("name", "property", "itemprop", "http-equiv"):
            key = str(meta.get(attr) or "").strip().lower()
            if key not in _META_PUBLISHED_AT_KEYS:
                continue
            value = str(
                meta.get("content")
                or meta.get("datetime")
                or meta.get("value")
                or ""
            ).strip()
            parsed = parse_datetime_text(value, default_year=default_year)
            if parsed is not None:
                return parsed

    for node in soup.find_all("time"):
        value = str(node.get("datetime") or node.get_text(" ", strip=True) or "").strip()
        parsed = parse_datetime_text(value, default_year=default_year)
        if parsed is not None:
            return parsed
        parsed = extract_datetime_from_text(value, default_year=default_year)
        if parsed is not None:
            return parsed

    for node in soup.find_all(True):
        classes = {str(value).strip().lower() for value in (node.get("class") or []) if str(value).strip()}
        if not classes.intersection(_STRUCTURED_DATE_CLASSES):
            continue
        value = node.get_text(" ", strip=True)
        if not value or len(value) > 80:
            continue
        parsed = parse_datetime_text(value, default_year=default_year)
        if parsed is not None:
            return parsed
        parsed = extract_datetime_from_text(value, default_year=default_year)
        if parsed is not None:
            return parsed

    text = soup.get_text("\n", strip=True)
    return extract_datetime_from_text(
        text,
        default_year=default_year,
        require_hint=require_hint,
    )


def extract_datetime_from_url(url: str | None) -> datetime | None:
    if not url:
        return None

    patterns = (
        re.compile(r"/t(\d{4})(\d{2})(\d{2})_"),
        re.compile(r"/(\d{4})(\d{2})/t\d+"),
        re.compile(r"/(\d{4})(\d{2})(\d{2})/"),
        re.compile(r"/(\d{4})/(\d{2})(\d{2})/"),
        re.compile(r"/(\d{4})/(\d{1,2})/(\d{1,2})/"),
        re.compile(r"/art/(\d{4})/(\d{1,2})/(\d{1,2})/"),
    )

    for pattern in patterns:
        match = pattern.search(url)
        if not match:
            continue
        try:
            if len(match.groups()) == 2:
                return datetime(int(match[1]), int(match[2]), 1)
            return datetime(int(match[1]), int(match[2]), int(match[3]))
        except ValueError:
            continue

    return None
