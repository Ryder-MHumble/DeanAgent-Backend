from app.services.intel.university.backfill import (
    pick_target_source_ids,
    summarize_missing_counts,
)


def test_summarize_missing_counts_only_counts_null_published_at():
    rows = [
        {"source_id": "xjtu_news", "published_at": None},
        {"source_id": "xjtu_news", "published_at": None},
        {"source_id": "sjtu_news", "published_at": "2026-04-23T00:00:00+00:00"},
        {"source_id": "sjtu_news", "published_at": None},
        {"source_id": "", "published_at": None},
    ]

    assert summarize_missing_counts(rows) == {
        "xjtu_news": 2,
        "sjtu_news": 1,
    }


def test_pick_target_source_ids_prefers_most_missing_sources():
    counts = {
        "xjtu_news": 125,
        "sjtu_news": 406,
        "xidian_news": 117,
        "fudan_news": 39,
    }

    assert pick_target_source_ids(counts, limit=3) == [
        "sjtu_news",
        "xjtu_news",
        "xidian_news",
    ]


def test_pick_target_source_ids_honors_explicit_sources():
    counts = {
        "xjtu_news": 125,
        "sjtu_news": 406,
    }

    assert pick_target_source_ids(
        counts,
        requested=["xjtu_news", "missing_source", "sjtu_news"],
    ) == ["xjtu_news", "sjtu_news"]
