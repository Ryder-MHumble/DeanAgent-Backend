from unittest.mock import AsyncMock, patch

import pytest

from app.services.core import source_service

MOCK_CONFIGS = [
    {
        "id": "leaders_tsinghua",
        "name": "清华大学-现任领导",
        "url": "https://example.com/leader",
        "dimension": "personnel",
        "dimension_name": "对人事",
        "group": "university_leadership_official",
        "tags": ["personnel", "leadership", "official"],
        "crawl_method": "university_leadership",
        "schedule": "weekly",
        "priority": 1,
        "is_enabled": True,
        "source_file": "university_leadership_sources.yaml",
    },
    {
        "id": "scholar_tsinghua",
        "name": "清华大学-师资",
        "url": "https://example.com/scholar",
        "dimension": "scholars",
        "dimension_name": "高校师资",
        "group": "tsinghua",
        "tags": ["faculty", "tsinghua", "ai"],
        "crawl_method": "faculty",
        "schedule": "weekly",
        "priority": 2,
        "is_enabled": False,
        "source_file": "scholar-tsinghua.yaml",
    },
    {
        "id": "policy_state_council",
        "name": "国务院政策",
        "url": "https://example.com/policy",
        "dimension": "national_policy",
        "dimension_name": "对国家",
        "group": "policy",
        "tags": ["policy", "state_council"],
        "crawl_method": "static",
        "schedule": "daily",
        "priority": 1,
        "is_enabled": True,
        "source_file": "national_policy.yaml",
    },
]

MOCK_STATES = {
    "leaders_tsinghua": {
        "last_crawl_at": "2026-03-29T10:00:00+00:00",
        "consecutive_failures": 0,
    },
    "scholar_tsinghua": {
        "is_enabled_override": True,
        "consecutive_failures": 1,
    },
    "policy_state_council": {
        "consecutive_failures": 3,
    },
}


def _mock_deps():
    merged_states: dict[str, dict] = {}
    for config in MOCK_CONFIGS:
        merged_states[config["id"]] = {
            "source_id": config["id"],
            "source_name": config["name"],
            "source_url": config["url"],
            "dimension": config["dimension"],
            "dimension_name": config["dimension_name"],
            "group_name": config["group"],
            "tags": config["tags"],
            "crawl_method": config["crawl_method"],
            "schedule": config["schedule"],
            "source_file": config["source_file"],
            "source_type": config.get("source_type"),
            "source_platform": config.get("source_platform"),
            "is_enabled_default": config["is_enabled"],
            "is_supported": True,
        }
        merged_states[config["id"]].update(MOCK_STATES.get(config["id"], {}))

    return patch(
        "app.services.core.source_service.get_all_source_states",
        new=AsyncMock(return_value=merged_states),
    )


@pytest.mark.asyncio
async def test_list_sources_supports_tag_and_enable_filters():
    with _mock_deps():
        result = await source_service.list_sources(
            tags="leadership,faculty",
            is_enabled=True,
            sort_by="id",
        )

    ids = {item["id"] for item in result}
    assert ids == {"leaders_tsinghua", "scholar_tsinghua"}
    scholar_item = next(item for item in result if item["id"] == "scholar_tsinghua")
    assert scholar_item["is_enabled"] is True
    assert scholar_item["is_enabled_overridden"] is True
    assert scholar_item["health_status"] == "warning"


@pytest.mark.asyncio
async def test_list_sources_filters_health_status():
    with _mock_deps():
        result = await source_service.list_sources(health_status="failing")

    assert len(result) == 1
    assert result[0]["id"] == "policy_state_council"
    assert result[0]["health_status"] == "failing"


@pytest.mark.asyncio
async def test_list_source_facets_returns_dimension_and_tags():
    with _mock_deps():
        facets = await source_service.list_source_facets(dimensions="personnel,scholars")

    dimensions = {item["key"]: item for item in facets["dimensions"]}
    assert dimensions["personnel"]["count"] == 1
    assert dimensions["personnel"]["enabled_count"] == 1
    assert dimensions["personnel"]["label"] == "组织人事动态"
    assert dimensions["scholars"]["count"] == 1
    assert dimensions["scholars"]["enabled_count"] == 1
    assert dimensions["scholars"]["label"] == "学者与师资库"
    tags = {item["key"]: item["count"] for item in facets["tags"]}
    assert tags["leadership"] == 1
    assert tags["faculty"] == 1


@pytest.mark.asyncio
async def test_list_sources_catalog_pagination_and_applied_filters():
    with _mock_deps():
        result = await source_service.list_sources_catalog(
            keyword="清华",
            page=1,
            page_size=1,
            sort_by="name",
            include_facets=True,
        )

    assert result["total_sources"] == 3
    assert result["filtered_sources"] == 2
    assert result["page"] == 1
    assert result["page_size"] == 1
    assert result["total_pages"] == 2
    assert len(result["items"]) == 1
    assert result["facets"] is not None
    assert result["applied_filters"]["keyword"] == "清华"


@pytest.mark.asyncio
async def test_list_sources_supports_taxonomy_filters_and_facets():
    with _mock_deps():
        result = await source_service.list_sources(
            taxonomy_domain="talent_personnel",
            taxonomy_track="university_leadership",
        )
        facets = await source_service.list_source_facets(taxonomy_domain="policy_governance")

    assert len(result) == 1
    assert result[0]["id"] == "leaders_tsinghua"
    assert result[0]["taxonomy_scope"] == "university"

    track_facets = {item["key"]: item for item in facets["taxonomy_tracks"]}
    assert "policy_national" in track_facets
