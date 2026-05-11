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


@pytest.mark.asyncio
async def test_department_filter_keeps_legacy_fallback_path(monkeypatch):
    calls = {"fast": 0, "fallback": 0}
    items = [
        {
            "id": "scholar-1",
            "name": "Alice",
            "university": "清华大学计算机学院",
            "department": "",
        }
    ]

    async def fake_query_scholar_list_fast(**kwargs):
        calls["fast"] += 1
        return {
            "total": 0,
            "page": 1,
            "page_size": 20,
            "total_pages": 1,
            "items": [],
        }

    async def fake_load_all_with_annotations():
        calls["fallback"] += 1
        return items

    async def fake_attach_scholar_activities(loaded_items):
        assert loaded_items is items

    def fake_apply_filters(loaded_items, **kwargs):
        assert loaded_items is items
        assert kwargs["department"] == "计算机学院"
        return loaded_items

    monkeypatch.setattr(
        scholar_service,
        "query_scholar_list_fast",
        fake_query_scholar_list_fast,
    )
    monkeypatch.setattr(
        scholar_service,
        "_load_all_with_annotations_async",
        fake_load_all_with_annotations,
    )
    monkeypatch.setattr(
        scholar_service,
        "_attach_scholar_activities",
        fake_attach_scholar_activities,
    )
    monkeypatch.setattr(scholar_service, "_apply_filters", fake_apply_filters)

    result = await scholar_service.get_scholar_list(department="计算机学院")

    assert result["total"] == 1
    assert calls == {"fast": 0, "fallback": 1}


@pytest.mark.asyncio
async def test_raw_university_resolution_preserves_primary_affiliation(monkeypatch):
    class FakePool:
        async def fetch(self, query):
            assert "SELECT DISTINCT university" in query
            return [
                {"university": "阿里巴巴集团"},
                {"university": "Alibaba Group"},
                {"university": "清华大学"},
            ]

    monkeypatch.setattr("app.db.pool.get_pool", lambda: FakePool())

    names = await scholar_service._resolve_raw_university_names_for_filter("阿里巴巴")

    assert names == ["阿里巴巴", "阿里巴巴集团", "Alibaba Group"]
