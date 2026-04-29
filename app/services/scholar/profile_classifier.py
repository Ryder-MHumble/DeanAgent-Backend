"""Rule-based scholar profile classification helpers.

The classifier is intentionally conservative: uncertain cases stay ``None`` so
the UI can show "待判定" instead of over-claiming identity or student status.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

RULE_VERSION = "scholar_profile_rules_v1"

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

_CHINESE_ORG_HINTS = (
    "中国",
    "北京",
    "上海",
    "清华",
    "北大",
    "浙江大学",
    "复旦",
    "南京大学",
    "中国科学技术大学",
    "哈尔滨工业大学",
    "国防科技大学",
    "中山大学",
    "华中科技大学",
    "武汉大学",
    "西安交通大学",
    "上海交通大学",
    "北京航空航天大学",
    "北京理工大学",
    "电子科技大学",
    "中国科学院",
)

_CHINA_COUNTRIES = {"cn", "china", "pr china", "p.r. china", "中国", "中华人民共和国"}
_NON_CHINA_COUNTRIES = {
    "us",
    "usa",
    "united states",
    "uk",
    "united kingdom",
    "canada",
    "australia",
    "germany",
    "france",
    "italy",
    "japan",
    "korea",
    "south korea",
    "singapore",
    "netherlands",
    "switzerland",
    "sweden",
}

_STUDENT_RE = re.compile(
    r"\b(phd|doctoral|master'?s?|msc|graduate|undergraduate|bachelor'?s?)\s+"
    r"(student|candidate|researcher)\b|"
    r"\b(student|doctoral candidate|phd candidate|graduate assistant)\b|"
    r"博士生|硕士生|研究生|本科生|在读博士|博士研究生|硕士研究生",
    re.IGNORECASE,
)

_NON_STUDENT_RE = re.compile(
    r"教授|副教授|讲师|导师|博导|硕导|研究员|副研究员|助理研究员|工程师|院士|"
    r"\b(professor|faculty|lecturer|scientist|researcher|engineer|director|"
    r"principal investigator|pi|chair|fellow)\b",
    re.IGNORECASE,
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _custom_fields(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("custom_fields")
    return dict(raw) if isinstance(raw, dict) else {}


def _metadata_profile(custom_fields: dict[str, Any]) -> dict[str, Any]:
    raw = custom_fields.get("metadata_profile")
    return dict(raw) if isinstance(raw, dict) else {}


def _text_blob(row: dict[str, Any], custom_fields: dict[str, Any]) -> str:
    metadata = _metadata_profile(custom_fields)
    parts: list[str] = [
        _clean(row.get("name")),
        _clean(row.get("name_en")),
        _clean(row.get("university")),
        _clean(row.get("department")),
        _clean(row.get("position")),
        _clean(row.get("bio")),
        _clean(metadata.get("current_institution")),
        _clean(metadata.get("current_department")),
        _clean(custom_fields.get("aaai_plus_org_all")),
        _clean(custom_fields.get("aaai_plus_org_main")),
        _clean(custom_fields.get("aaai_plus_education")),
    ]
    return " ".join(part for part in parts if part)


def _role_text_blob(row: dict[str, Any], custom_fields: dict[str, Any]) -> str:
    metadata = _metadata_profile(custom_fields)
    parts: list[str] = [
        _clean(row.get("position")),
        _clean(metadata.get("current_degree_stage")),
        _clean(metadata.get("current_department")),
    ]
    return " ".join(part for part in parts if part)


def classify_is_chinese(row: dict[str, Any]) -> bool | None:
    custom_fields = _custom_fields(row)
    metadata = _metadata_profile(custom_fields)
    country = _clean(custom_fields.get("org_country")).lower()
    text = _text_blob(row, custom_fields)

    if _CJK_RE.search(_clean(row.get("name"))) or _CJK_RE.search(_clean(row.get("name_en"))):
        return True
    if country in _CHINA_COUNTRIES:
        return True
    if any(hint in text for hint in _CHINESE_ORG_HINTS):
        return True
    if country in _NON_CHINA_COUNTRIES:
        return False
    return None


def classify_is_current_student(row: dict[str, Any]) -> bool | None:
    custom_fields = _custom_fields(row)
    role_text = _role_text_blob(row, custom_fields)
    if _NON_STUDENT_RE.search(role_text):
        return False
    if _STUDENT_RE.search(role_text):
        return True
    return None


def classify_scholar_profile(row: dict[str, Any]) -> dict[str, Any]:
    """Return merged custom_fields plus classifier output groups."""
    custom_fields = _custom_fields(row)
    metadata = _metadata_profile(custom_fields)
    is_chinese = classify_is_chinese(row)
    is_current_student = classify_is_current_student(row)
    updated_at = datetime.now(UTC).isoformat()

    profile_flags = {
        "is_chinese": is_chinese,
        "is_current_student": is_current_student,
        "rule_version": RULE_VERSION,
        "updated_at": updated_at,
        "identity_note": (
            "Rule-based conservative classifier; null means insufficient signal. "
            "supervised_students linkage is not treated as current student evidence."
        ),
    }
    metadata_profile = {
        **metadata,
        "is_chinese": is_chinese,
        "is_current_student": is_current_student,
        "last_classified_at": updated_at,
        "classifier_rule_version": RULE_VERSION,
    }

    merged_custom_fields = {
        **custom_fields,
        "profile_flags": profile_flags,
        "metadata_profile": metadata_profile,
    }
    return {
        "profile_flags": profile_flags,
        "metadata_profile": metadata_profile,
        "custom_fields": merged_custom_fields,
    }
