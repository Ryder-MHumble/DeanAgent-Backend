"""Filtering helpers for scholar queries."""
from __future__ import annotations

import json
from typing import Any

# ---------------------------------------------------------------------------
# Institution classification map (from DB, cached in-process)
# ---------------------------------------------------------------------------

_INSTITUTION_CLASSIFICATION_CACHE: dict[str, dict[str, str]] | None = None


_TYPE_TO_ORG_TYPE: dict[str, str] = {
    "university": "高校",
    "company": "企业",
    "research_institute": "研究机构",
    "academic_society": "其他",
}

# Groups that indicate international institutions
_INTL_GROUPS = {"海外高校"}


async def get_institution_classification_map() -> dict[str, dict[str, str]]:
    """Return {institution_name: {region, org_type}} from institutions service.

    Fetches from Supabase institutions table with complete classification data.
    Fetches once per process and caches the result.
    Falls back to empty dict on error (callers will use heuristics).
    """
    global _INSTITUTION_CLASSIFICATION_CACHE
    if _INSTITUTION_CLASSIFICATION_CACHE is not None:
        return _INSTITUTION_CLASSIFICATION_CACHE

    try:
        from app.services.core.institution.storage import fetch_all_institutions  # noqa: PLC0415

        # Get all institutions from database
        institutions = await fetch_all_institutions()

        mapping: dict[str, dict[str, str]] = {}
        for inst in institutions:
            name = (inst.get("name") or "").strip()
            if not name:
                continue

            # Use region and org_type directly from database
            region = inst.get("region") or ""
            org_type = inst.get("org_type") or ""

            mapping[name] = {"region": region, "org_type": org_type}

        _INSTITUTION_CLASSIFICATION_CACHE = mapping
        return mapping
    except Exception as exc:
        # Log error but don't crash - fall back to heuristics
        import logging  # noqa: PLC0415
        logging.getLogger(__name__).warning(
            "Failed to load institution classification map: %s", exc
        )
        return {}


def invalidate_institution_classification_cache() -> None:
    """Call this when institution data changes."""
    global _INSTITUTION_CLASSIFICATION_CACHE
    _INSTITUTION_CLASSIFICATION_CACHE = None


def _get_region(university: str, inst_map: dict[str, dict[str, str]]) -> str:
    """Resolve region for a university name using DB map first, heuristics as fallback."""
    if university in inst_map and inst_map[university].get("region"):
        return inst_map[university]["region"]
    return _derive_region_from_university(university)


def _get_org_type(university: str, inst_map: dict[str, dict[str, str]]) -> str:
    """Resolve org_type for a university name using DB map first, heuristics as fallback."""
    if university in inst_map and inst_map[university].get("org_type"):
        return inst_map[university]["org_type"]
    return _derive_affiliation_type_from_university(university)


def _normalize_exact_text(value: Any) -> str:
    """Normalize text for exact-match comparison.

    Rules:
    - trim leading/trailing spaces
    - collapse consecutive whitespace to a single space
    - lowercase (for case-insensitive exact match)
    """
    if value is None:
        return ""
    return " ".join(str(value).strip().split()).lower()


def _match_exact(value: str, query: str) -> bool:
    return _normalize_exact_text(value) == _normalize_exact_text(query)


def _norm_token(value: Any) -> str:
    if value is None:
        return ""
    return "".join(str(value).strip().split()).lower()


def _to_text_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        return [text]
    return []


def _coerce_custom_fields(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _community_matches(item: dict[str, Any], community_name: str | None, community_type: str | None) -> bool:
    if not community_name and not community_type:
        return True

    custom_fields = _coerce_custom_fields(item.get("custom_fields"))

    tags_raw = _to_text_list(item.get("tags"))
    community_tags_raw = _to_text_list(custom_fields.get("community_tags"))
    pool = tags_raw + community_tags_raw

    name_target = _norm_token(community_name) if community_name else ""
    type_target = _norm_token(community_type) if community_type else ""

    def _pool_has(target: str) -> bool:
        if not target:
            return True
        for tag in pool:
            token = _norm_token(tag)
            if not token:
                continue
            if token == target:
                return True
            if ":" in token and token.split(":")[-1] == target:
                return True
        return False

    if name_target:
        cf_name = _norm_token(custom_fields.get("community_name"))
        if cf_name != name_target and not _pool_has(name_target):
            return False

    if type_target:
        cf_type = _norm_token(custom_fields.get("community_type"))
        if cf_type != type_target and not _pool_has(type_target):
            return False

    return True


def _extract_project_tags(item: dict[str, Any]) -> list[dict[str, str]]:
    raw_tags = item.get("project_tags")
    tags: list[dict[str, str]] = []
    if isinstance(raw_tags, list):
        for raw in raw_tags:
            if not isinstance(raw, dict):
                continue
            category = str(raw.get("category") or "").strip()
            subcategory = str(raw.get("subcategory") or "").strip()
            if not category and not subcategory:
                continue
            tags.append(
                {
                    "category": category,
                    "subcategory": subcategory,
                }
            )
    if tags:
        return tags

    legacy_category = str(item.get("project_category") or "").strip()
    legacy_subcategory = str(item.get("project_subcategory") or "").strip()
    if not legacy_category and not legacy_subcategory:
        return []
    return [{"category": legacy_category, "subcategory": legacy_subcategory}]


def _extract_event_tags(item: dict[str, Any]) -> list[dict[str, str]]:
    raw_tags = item.get("event_tags")
    tags: list[dict[str, str]] = []
    if not isinstance(raw_tags, list):
        return tags
    for raw in raw_tags:
        if not isinstance(raw, dict):
            continue
        category = str(raw.get("category") or "").strip()
        series = str(raw.get("series") or "").strip()
        event_type = str(raw.get("event_type") or "").strip()
        if not category and not series and not event_type:
            continue
        tags.append(
            {
                "category": category,
                "series": series,
                "event_type": event_type,
            }
        )
    return tags


_PROJECT_SUBCATEGORY_ALIASES: dict[str, set[str]] = {
    "学院学生高校导师": {"学院学生事务导师"},
    "学院学生事务导师": {"学院学生高校导师"},
    "科技教育委员会": {"科技育青委员会"},
    "科技育青委员会": {"科技教育委员会"},
}


def _project_subcategory_targets(value: str) -> set[str]:
    target = value.strip()
    if not target:
        return set()
    targets = {target}
    targets.update(_PROJECT_SUBCATEGORY_ALIASES.get(target, set()))
    return targets


def _is_cobuild_scholar(
    item: dict[str, Any],
    project_tags: list[dict[str, str]],
    event_tags: list[dict[str, str]],
) -> bool:
    if project_tags or event_tags:
        return True
    explicit = item.get("is_cobuild_scholar")
    if isinstance(explicit, bool):
        return explicit
    return False


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

    # Known domestic keywords (Chinese institutions with non-Chinese chars)
    domestic_keywords = [
        "中科院", "中国科学院", "中国工程院", "中关村", "昌平",
        "深圳", "上海", "北京", "香港", "澳门",
    ]
    if any(kw in university for kw in domestic_keywords):
        return "国内"

    # Known international universities (English names)
    intl_keywords = [
        "University", "Institute", "College", "School",
        "MIT", "Stanford", "Harvard", "Berkeley", "CMU",
        "Oxford", "Cambridge", "ETH", "EPFL",
        "NUS", "NTU", "KAIST", "Tokyo",
        "A*STAR", "CNRS", "INRIA", "Max Planck",
        "UCLA", "USC", "Caltech", "Georgia Tech",
    ]

    if any(kw in university for kw in intl_keywords):
        return "国际"

    # Pure English name (no Chinese chars) → treat as 国际
    return "国际"


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
    if any(kw in uni_lower for kw in [
        "大学", "学院", "university", "college",
        "ucla", "usc", "mit", "caltech", "georgia tech",
    ]):
        return "高校"

    # 研究机构 keywords
    if any(kw in uni_lower for kw in [
        "研究院", "研究所", "研究中心", "科学院", "工程院",
        "实验室", "中科院", "自动化所", "计算所", "软件所",
        "数学所", "物理所", "化学所", "生物所",
        "institute", "laboratory", "lab", "research center",
        "a*star", "cnrs", "inria", "max planck",
    ]):
        return "研究机构"

    # 企业 keywords
    if any(kw in uni_lower for kw in [
        "公司", "集团", "企业",
        "company", "corp", "inc", "ltd",
        "亚马逊", "谷歌", "微软", "华为", "腾讯", "阿里", "百度", "字节",
        "amazon", "google", "microsoft", "meta", "apple",
        "科技", "technology", "tech",
    ]):
        # Exclude false positives: "大学" or "学院" in name takes precedence
        if not any(kw in uni_lower for kw in ["大学", "学院", "university", "college"]):
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
    project_category: str | None,
    project_subcategory: str | None,
    participated_event_id: str | None,
    is_cobuild_scholar: bool | None,
    region: str | None,
    affiliation_type: str | None,
    institution_names: list[str] | None = None,
    custom_field_key: str | None = None,
    custom_field_value: str | None = None,
    inst_map: dict[str, dict[str, str]] | None = None,
    community_name: str | None = None,
    community_type: str | None = None,
) -> list[dict[str, Any]]:
    result = items

    # institution_names: exact-match on university field (used by institution_group/category filter)
    if institution_names is not None:
        name_set = set(institution_names)
        result = [i for i in result if (i.get("university") or "") in name_set]

    if university:
        result = [i for i in result if _match_exact(i.get("university", ""), university)]

    if department:
        result = [i for i in result if _match_exact(i.get("department", ""), department)]

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

    _map = inst_map or {}
    if region:
        result = [
            i for i in result
            if _get_region(i.get("university", ""), _map) == region
        ]

    if affiliation_type:
        result = [
            i for i in result
            if _get_org_type(i.get("university", ""), _map) == affiliation_type
        ]

    if community_name or community_type:
        result = [i for i in result if _community_matches(i, community_name, community_type)]

    if project_category:
        target = project_category.strip()
        result = [
            i for i in result
            if any((tag.get("category") or "") == target for tag in _extract_project_tags(i))
        ]

    if project_subcategory:
        targets = _project_subcategory_targets(project_subcategory)
        result = [
            i for i in result
            if any((tag.get("subcategory") or "") in targets for tag in _extract_project_tags(i))
        ]

    if participated_event_id:
        target = participated_event_id.strip()

        def _has_event(item: dict[str, Any]) -> bool:
            event_ids = item.get("participated_event_ids") or []
            if isinstance(event_ids, list):
                return target in event_ids
            return False

        result = [i for i in result if _has_event(i)]

    if is_cobuild_scholar is not None:
        result = [
            i for i in result
            if _is_cobuild_scholar(
                i,
                _extract_project_tags(i),
                _extract_event_tags(i),
            )
            == is_cobuild_scholar
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

    if custom_field_key:
        result = [
            i for i in result
            if _coerce_custom_fields(i.get("custom_fields")).get(custom_field_key) == custom_field_value
        ]

    return result
