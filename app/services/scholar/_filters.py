"""Filtering helpers for scholar queries."""
from __future__ import annotations

from typing import Any


def _match_fuzzy(value: str, query: str) -> bool:
    return query.strip().lower() in (value or "").lower()


def _derive_region_from_university(university: str) -> str:
    """Derive region (国内/国际) from university name.

    Rules:
    - 国内: Chinese universities (contains Chinese characters or known domestic names)
    - 国际: International universities (primarily English names without Chinese)
    """
    if not university:
        return ""

    # Check if contains Chinese characters
    has_chinese = any('\u4e00' <= c <= '\u9fff' for c in university)
    if has_chinese:
        return "国内"

    # Known international universities (English names)
    intl_keywords = [
        "University", "Institute", "College", "School",
        "MIT", "Stanford", "Harvard", "Berkeley", "CMU",
        "Oxford", "Cambridge", "ETH", "EPFL",
        "NUS", "NTU", "KAIST", "Tokyo"
    ]

    if any(kw in university for kw in intl_keywords):
        return "国际"

    # Default to 国内 if uncertain (most scholars in DB are domestic)
    return "国内"


def _derive_affiliation_type_from_university(university: str) -> str:
    """Derive affiliation_type (高校/企业/研究机构/其他) from university name.

    Rules:
    - 高校: Contains 大学/学院/University/College
    - 研究机构: Contains 研究院/研究所/研究中心/Institute/Laboratory/Lab
    - 企业: Contains 公司/集团/科技/Company/Corp/Inc
    - 其他: Everything else
    """
    if not university:
        return ""

    uni_lower = university.lower()

    # 高校 keywords
    if any(kw in uni_lower for kw in ["大学", "学院", "university", "college"]):
        return "高校"

    # 研究机构 keywords
    if any(kw in uni_lower for kw in [
        "研究院", "研究所", "研究中心", "科学院", "工程院",
        "institute", "laboratory", "lab", "research center"
    ]):
        return "研究机构"

    # 企业 keywords
    if any(kw in uni_lower for kw in [
        "公司", "集团", "科技", "技术", "企业",
        "company", "corp", "inc", "ltd", "technology", "tech"
    ]):
        return "企业"

    return "其他"


def _apply_filters(
    items: list[dict[str, Any]],
    *,
    university: str | None,
    department: str | None,
    position: str | None,
    is_academician: bool | None,
    is_potential_recruit: bool | None,
    is_advisor_committee: bool | None,
    is_adjunct_supervisor: bool | None,
    has_email: bool | None,
    keyword: str | None,
    region: str | None,
    affiliation_type: str | None,
) -> list[dict[str, Any]]:
    result = items

    if university:
        result = [i for i in result if _match_fuzzy(i.get("university", ""), university)]

    if department:
        result = [i for i in result if _match_fuzzy(i.get("department", ""), department)]

    if position:
        result = [i for i in result if i.get("position", "") == position]

    if is_academician is not None:
        result = [i for i in result if bool(i.get("is_academician", False)) == is_academician]

    if is_potential_recruit is not None:
        result = [i for i in result if bool(i.get("is_potential_recruit", False)) == is_potential_recruit]

    if is_advisor_committee is not None:
        result = [i for i in result if bool(i.get("is_advisor_committee", False)) == is_advisor_committee]

    if is_adjunct_supervisor is not None:
        def _has_adjunct(item: dict[str, Any]) -> bool:
            adj = item.get("adjunct_supervisor")
            if isinstance(adj, dict):
                return bool(adj.get("status", ""))
            return False
        result = [i for i in result if _has_adjunct(i) == is_adjunct_supervisor]

    if has_email is not None:
        result = [i for i in result if bool(i.get("email", "")) == has_email]

    if region:
        result = [
            i for i in result
            if _derive_region_from_university(i.get("university", "")) == region
        ]

    if affiliation_type:
        result = [
            i for i in result
            if _derive_affiliation_type_from_university(i.get("university", "")) == affiliation_type
        ]

    if keyword:
        kw = keyword.strip().lower()

        def _matches(i: dict[str, Any]) -> bool:
            if kw in (i.get("name") or "").lower():
                return True
            if kw in (i.get("name_en") or "").lower():
                return True
            if kw in (i.get("bio") or "").lower():
                return True
            if any(kw in area.lower() for area in (i.get("research_areas") or [])):
                return True
            if any(kw in kw_tag.lower() for kw_tag in (i.get("keywords") or [])):
                return True
            return False

        result = [i for i in result if _matches(i)]

    return result
