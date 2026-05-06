from app.services.scholar._achievement_tags import extract_achievement_tags
from app.services.scholar._fast_query import _build_where_clause
from app.services.scholar._filters import _apply_filters


def _run_filters(items, **overrides):
    kwargs = {
        "university": None,
        "department": None,
        "position": None,
        "is_academician": None,
        "is_potential_recruit": None,
        "is_advisor_committee": None,
        "is_adjunct_supervisor": None,
        "has_email": None,
        "keyword": None,
        "project_category": None,
        "project_subcategory": None,
        "project_categories": None,
        "project_subcategories": None,
        "event_types": None,
        "participated_event_id": None,
        "is_cobuild_scholar": None,
        "is_chinese": None,
        "is_current_student": None,
        "chinese_identity": None,
        "achievement_tag": None,
        "achievement_tags": None,
        "region": None,
        "affiliation_type": None,
        "institution_names": None,
        "custom_field_key": None,
        "custom_field_value": None,
        "inst_map": {},
        "community_name": None,
        "community_type": None,
    }
    kwargs.update(overrides)
    return _apply_filters(items, **kwargs)


def test_extract_achievement_tags_includes_scholar_activities():
    tags = extract_achievement_tags(
        scholar_activities=[
            {"activity_des": "ICML 2026 SCALE Workshops Invited Speakers"},
            {"activity_des": "AAAI 2026 Causal AI Workshops Organizers"},
        ]
    )

    assert tags == ["ICML", "AAAI"]


def test_activity_only_scholar_matches_achievement_filter():
    items = [
        {
            "name": "A",
            "achievement_tags": [],
            "representative_publications": [],
            "awards": [],
            "scholar_activities": [
                {"activity_des": "ICML 2026 SCALE Workshops Invited Speakers"}
            ],
        },
        {
            "name": "B",
            "achievement_tags": [],
            "representative_publications": [],
            "awards": [],
            "scholar_activities": [
                {"activity_des": "AAAI 2026 AI Safety Workshops Invited Speakers"}
            ],
        },
    ]

    filtered = _run_filters(items, achievement_tags="ICML:2026")

    assert [item["name"] for item in filtered] == ["A"]


def test_fast_achievement_filter_includes_scholar_activities_sql():
    where_sql, params = _build_where_clause(
        university=None,
        department=None,
        position=None,
        is_academician=None,
        is_potential_recruit=None,
        is_advisor_committee=None,
        is_adjunct_supervisor=None,
        has_email=None,
        keyword=None,
        is_chinese=None,
        is_current_student=None,
        chinese_identity=None,
        achievement_tag=None,
        achievement_tags="ICML:2026",
        custom_field_key=None,
        custom_field_value=None,
        allowed_universities=None,
        has_representative_publications_column=True,
        has_scholar_activities_table=True,
    )

    assert "scholar_activities sa" in where_sql
    assert "representative_publications" in where_sql
    assert "%icml%" in params
    assert 2026 in params


def test_fast_achievement_filter_skips_missing_materialized_tag_column():
    where_sql, params = _build_where_clause(
        university=None,
        department=None,
        position=None,
        is_academician=None,
        is_potential_recruit=None,
        is_advisor_committee=None,
        is_adjunct_supervisor=None,
        has_email=None,
        keyword=None,
        is_chinese=None,
        is_current_student=None,
        chinese_identity=None,
        achievement_tag=None,
        achievement_tags="ICML",
        custom_field_key=None,
        custom_field_value=None,
        allowed_universities=None,
        has_achievement_tags_column=False,
        has_representative_publications_column=True,
        has_scholar_activities_table=False,
    )

    assert "achievement_tags &&" not in where_sql
    assert "scholar_publications sp" in where_sql
    assert "representative_publications" in where_sql
    assert "scholar_activities sa" not in where_sql
    assert params == [["%icml%"]]
