import pytest

import app.services.scholar as scholar_service


@pytest.mark.asyncio
async def test_university_filter_uses_fast_path_with_resolved_raw_names(monkeypatch):
    calls = {}

    async def fake_resolve_raw_universities(university):
        assert university == "360集团"
        return ["360集团"]

    async def fake_query_scholar_list_fast(**kwargs):
        calls.update(kwargs)
        return {
            "total": 3,
            "page": 1,
            "page_size": 20,
            "total_pages": 1,
            "items": [],
        }

    async def fail_load_all_with_annotations():
        raise AssertionError("fallback path should not load all scholars")

    monkeypatch.setattr(
        scholar_service,
        "_resolve_raw_university_names_for_filter",
        fake_resolve_raw_universities,
        raising=False,
    )
    monkeypatch.setattr(
        scholar_service,
        "query_scholar_list_fast",
        fake_query_scholar_list_fast,
    )
    monkeypatch.setattr(
        scholar_service,
        "_load_all_with_annotations_async",
        fail_load_all_with_annotations,
    )

    result = await scholar_service.get_scholar_list(university="360集团")

    assert result["total"] == 3
    assert calls["university"] is None
    assert calls["institution_names"] == ["360集团"]
