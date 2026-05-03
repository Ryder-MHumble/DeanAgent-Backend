from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.academic import venues
from app.api.content import articles, sources
from app.api.social import social_posts
from app.config import settings
from app.db.client import close_client, init_client
from app.db.pool import close_pool, init_pool


def _build_test_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await close_client()
        await close_pool()
        await init_pool(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
        )
        await init_client(backend="postgres")
        try:
            yield
        finally:
            await close_client()
            await close_pool()

    app = FastAPI(lifespan=lifespan)
    app.include_router(articles.router, prefix="/api/v1/articles")
    app.include_router(social_posts.router, prefix="/api/v1/social-posts")
    app.include_router(sources.router, prefix="/api/v1/sources")
    app.include_router(venues.router, prefix="/api/v1/venues")
    return app


@pytest.fixture(scope="module")
def api_client():
    with TestClient(_build_test_app(), raise_server_exceptions=False) as client:
        yield client


def _assert_paginated_response_shape(payload: dict):
    assert "items" in payload
    assert "total" in payload
    assert "page" in payload
    assert "page_size" in payload
    assert "total_pages" in payload


def test_articles_keyword_with_comma_returns_200(api_client: TestClient):
    response = api_client.get(
        "/api/v1/articles",
        params={"source_name": "清华", "keyword": "OpenAI,Anthropic", "page": 1, "page_size": 1},
    )

    assert response.status_code == 200
    _assert_paginated_response_shape(response.json())


def test_articles_date_from_returns_200(api_client: TestClient):
    response = api_client.get(
        "/api/v1/articles",
        params={"source_name": "清华", "date_from": "2026-04-20", "page": 1, "page_size": 1},
    )

    assert response.status_code == 200
    _assert_paginated_response_shape(response.json())


def test_articles_date_to_datetime_returns_200(api_client: TestClient):
    response = api_client.get(
        "/api/v1/articles",
        params={
            "source_name": "清华",
            "date_to": "2026-04-20T23:59:59+00:00",
            "page": 1,
            "page_size": 1,
        },
    )

    assert response.status_code == 200
    _assert_paginated_response_shape(response.json())


def test_social_posts_keyword_with_comma_returns_200(api_client: TestClient):
    response = api_client.get(
        "/api/v1/social-posts",
        params={
            "source_id": "twitter_ai_kol_international",
            "keyword": "OpenAI,Anthropic",
            "page": 1,
            "page_size": 1,
        },
    )

    assert response.status_code == 200
    _assert_paginated_response_shape(response.json())


def test_venues_keyword_with_comma_returns_200(api_client: TestClient):
    response = api_client.get(
        "/api/v1/venues",
        params={"keyword": "OpenAI,Anthropic", "page": 1, "page_size": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "total" in payload
    assert "page" in payload
    assert "page_size" in payload
    assert "total_pages" in payload


def test_source_items_keyword_with_comma_returns_200(api_client: TestClient):
    response = api_client.get(
        "/api/v1/sources/items",
        params={"source_name": "清华", "keyword": "OpenAI,Anthropic", "page": 1, "page_size": 1},
    )

    assert response.status_code == 200
    _assert_paginated_response_shape(response.json())


def test_source_items_date_filter_returns_200(api_client: TestClient):
    response = api_client.get(
        "/api/v1/sources/items",
        params={"source_name": "清华", "date_from": "2026-04-20", "page": 1, "page_size": 1},
    )

    assert response.status_code == 200
    _assert_paginated_response_shape(response.json())
