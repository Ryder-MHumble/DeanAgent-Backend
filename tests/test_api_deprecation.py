from fastapi import Response

from app.api.deprecation import (
    DEPRECATION_DOCS_PATH,
    get_deprecation_items,
    get_replacement_map,
    apply_deprecation_headers,
)


def test_get_replacement_map_contains_known_paths():
    replacement_map = get_replacement_map()
    assert replacement_map == {}


def test_apply_deprecation_headers_sets_standard_headers():
    response = Response(content="ok")
    apply_deprecation_headers(
        response,
        replacement_path="/api/v1/articles",
    )

    assert response.headers["Deprecation"] == "true"
    assert response.headers["X-Replacement-Endpoint"] == "/api/v1/articles"
    assert DEPRECATION_DOCS_PATH in response.headers["Link"]


def test_deprecation_items_have_required_fields():
    items = get_deprecation_items()
    assert items == []
    for item in items:
        assert item["method"]
        assert item["path"]
        assert item["replacement_path"]
        assert item["sunset_date"]
