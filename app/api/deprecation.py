"""Helpers for deprecation response headers."""
from __future__ import annotations

from fastapi import Response

DEFAULT_SUNSET = "Thu, 31 Dec 2026 23:59:59 GMT"
DEFAULT_SUNSET_DATE = "2026-12-31"
DEPRECATION_DOCS_PATH = "/api/v1/sources/deprecations"

DEPRECATED_ENDPOINTS = [
    {
        "method": "GET",
        "path": "/api/v1/articles/search",
        "replacement_path": "/api/v1/articles",
        "sunset_date": DEFAULT_SUNSET_DATE,
        "note": "参数与列表接口一致，建议统一改用列表接口。",
    },
    {
        "method": "GET",
        "path": "/api/v1/social-posts/search",
        "replacement_path": "/api/v1/social-posts",
        "sunset_date": DEFAULT_SUNSET_DATE,
        "note": "参数与列表接口一致，建议统一改用列表接口。",
    },
]


def get_deprecation_items() -> list[dict[str, str]]:
    return [dict(item) for item in DEPRECATED_ENDPOINTS]


def get_replacement_map() -> dict[str, str]:
    return {item["path"]: item["replacement_path"] for item in DEPRECATED_ENDPOINTS}


def apply_deprecation_headers(
    response: Response,
    *,
    replacement_path: str,
    docs_path: str = DEPRECATION_DOCS_PATH,
    sunset: str = DEFAULT_SUNSET,
) -> None:
    """Attach standardized deprecation headers to a response."""
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = sunset
    response.headers["X-Replacement-Endpoint"] = replacement_path

    links = [
        f'<{replacement_path}>; rel="alternate"; title="replacement endpoint"',
    ]
    if docs_path:
        links.append(f'<{docs_path}>; rel="deprecation"; type="application/json"')
    response.headers["Link"] = ", ".join(links)
