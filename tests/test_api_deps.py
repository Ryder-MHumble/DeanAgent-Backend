from fastapi import HTTPException

from app.api.deps import get_article_search_params


def test_get_article_search_params_empty_dates_are_none():
    params = get_article_search_params(
        dimension=None,
        source_id_filter=None,
        source_ids=None,
        source_name=None,
        source_names=None,
        keyword=None,
        date_from="",
        date_to="   ",
        sort_by="crawled_at",
        order="desc",
        page=1,
        page_size=20,
        custom_field_key=None,
        custom_field_value=None,
    )
    assert params.date_from is None
    assert params.date_to is None


def test_get_article_search_params_invalid_date_returns_422():
    try:
        get_article_search_params(
            dimension=None,
            source_id_filter=None,
            source_ids=None,
            source_name=None,
            source_names=None,
            keyword=None,
            date_from="not-a-date",
            date_to=None,
            sort_by="crawled_at",
            order="desc",
            page=1,
            page_size=20,
            custom_field_key=None,
            custom_field_value=None,
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        return
    raise AssertionError("Expected HTTPException(422) for invalid date input")
