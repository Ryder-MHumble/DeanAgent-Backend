from datetime import date, datetime, timezone

from app.db.client import _coerce_comparison_value, _split_or_expression


def test_split_or_expression_keeps_commas_inside_ilike_values():
    expression = "title.ilike.%OpenAI,Anthropic%,content.ilike.%OpenAI,Anthropic%"

    assert _split_or_expression(expression) == [
        "title.ilike.%OpenAI,Anthropic%",
        "content.ilike.%OpenAI,Anthropic%",
    ]


def test_coerce_comparison_value_parses_iso_date_for_date_columns():
    assert _coerce_comparison_value("event_date", "2026-04-20") == date(2026, 4, 20)


def test_coerce_comparison_value_parses_iso_datetime_for_timestamp_columns():
    assert _coerce_comparison_value(
        "published_at",
        "2026-04-20T23:59:59+00:00",
    ) == datetime(2026, 4, 20, 23, 59, 59, tzinfo=timezone.utc)


def test_coerce_comparison_value_leaves_non_temporal_columns_unchanged():
    assert _coerce_comparison_value("title", "2026-04-20") == "2026-04-20"
