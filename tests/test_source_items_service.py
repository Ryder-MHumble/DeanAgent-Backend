from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.article import ArticleSearchParams
from app.services.core import source_service


@pytest.mark.asyncio
async def test_list_source_items_requires_source_filter():
    params = ArticleSearchParams(page=1, page_size=20)

    with pytest.raises(ValueError):
        await source_service.list_source_items(params, require_source_filter=True)


@pytest.mark.asyncio
async def test_list_source_items_passes_through_to_article_service():
    params = ArticleSearchParams(source_name="清华", page=1, page_size=20)
    expected = {"items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0}

    with patch(
        "app.services.core.source_service.article_service.list_articles",
        new=AsyncMock(return_value=expected),
    ) as mocked_list:
        result = await source_service.list_source_items(params)

    assert result == expected
    mocked_list.assert_awaited_once_with(params)


@pytest.mark.asyncio
async def test_list_source_items_for_source_overrides_query_source_filters():
    params = ArticleSearchParams(
        source_name="清华",
        source_ids="a,b",
        keyword="AI",
        page=2,
        page_size=10,
    )
    expected = {"items": [], "total": 0, "page": 2, "page_size": 10, "total_pages": 0}

    with patch(
        "app.services.core.source_service.get_source",
        new=AsyncMock(return_value={"id": "leaders_tsinghua"}),
    ), patch(
        "app.services.core.source_service.article_service.list_articles",
        new=AsyncMock(return_value=expected),
    ) as mocked_list:
        result = await source_service.list_source_items_for_source("leaders_tsinghua", params)

    assert result == expected
    called_params = mocked_list.await_args.args[0]
    assert called_params.source_id == "leaders_tsinghua"
    assert called_params.source_ids is None
    assert called_params.source_name is None
    assert called_params.source_names is None
    assert called_params.keyword == "AI"


@pytest.mark.asyncio
async def test_list_source_items_for_source_returns_none_when_source_missing():
    params = ArticleSearchParams(page=1, page_size=20)

    with patch(
        "app.services.core.source_service.get_source",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.services.core.source_service.article_service.list_articles",
        new=AsyncMock(),
    ) as mocked_list:
        result = await source_service.list_source_items_for_source("missing", params)

    assert result is None
    mocked_list.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_sources_returns_recommended_endpoint():
    mock_catalog = {
        "items": [
            {
                "id": "leaders_tsinghua",
                "name": "清华大学-现任领导",
                "dimension": "personnel",
                "group": "university_leadership_official",
                "source_type": "university_leadership",
                "source_platform": "web",
                "is_enabled": True,
            }
        ],
        "filtered_sources": 1,
        "total_pages": 1,
    }

    with patch(
        "app.services.core.source_service.list_sources_catalog",
        new=AsyncMock(return_value=mock_catalog),
    ):
        result = await source_service.resolve_sources(q="清华", page=1, page_size=20)

    assert result["total"] == 1
    assert result["items"][0]["id"] == "leaders_tsinghua"
    assert (
        result["items"][0]["recommended_endpoint"]
        == "/api/sources/leaders_tsinghua/items"
    )


@pytest.mark.asyncio
async def test_resolve_sources_with_exact_source_id():
    with patch(
        "app.services.core.source_service.get_source",
        new=AsyncMock(
            return_value={
                "id": "policy_state_council",
                "name": "国务院政策",
                "dimension": "national_policy",
            }
        ),
    ):
        result = await source_service.resolve_sources(source_id="policy_state_council")

    assert result["total"] == 1
    assert result["items"][0]["id"] == "policy_state_council"
    assert result["page"] == 1


def test_list_api_deprecations_has_items():
    result = source_service.list_api_deprecations()
    assert result["total"] == 0
    assert result["items"] == []
