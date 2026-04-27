from __future__ import annotations

from app.scheduler.manager import load_all_source_configs

EXPECTED_TALENT_SCOUT_SOURCE_IDS = {
    "ccf_bdci",
    "aliyun_tianchi",
    "clue_benchmark",
    "semeval_conll",
    "neurips_competition",
    "robomaster",
    "tencent_hok_ai",
    "kaggle_grandmaster",
    "kdd_cup",
    "icpc_rankings",
    "huawei_elite_challenge",
    "casp",
    "igem",
    "ecmwf_ai_challenge",
    "noi_ioi",
    "ccpc",
    "lanqiao",
    "asc_competition",
    "sc_student_cluster",
    "isc_student_cluster",
    "pacman_huawei",
    "ctftime",
    "ciscn_student",
    "os_kernel_competition",
    "icra_competition",
    "world_robot_contest",
    "dblp_author",
    "arxiv_author",
    "semantic_scholar_author",
    "openreview_author",
    "academic_paper_authors",
    "acl_anthology_author",
    "cvf_openaccess_author",
    "github_ai_users",
    "github_ai_repo_contributors",
}


def test_talent_scout_yaml_loads_all_expected_sources():
    configs = load_all_source_configs()
    talent_configs = [cfg for cfg in configs if cfg.get("dimension") == "talent_scout"]

    ids = {cfg["id"] for cfg in talent_configs}
    assert ids == EXPECTED_TALENT_SCOUT_SOURCE_IDS
    assert {cfg.get("source_file") for cfg in talent_configs} == {"talent_scout.yaml"}


def test_talent_scout_sources_expose_required_contract_fields():
    configs = load_all_source_configs()
    talent_configs = [cfg for cfg in configs if cfg.get("dimension") == "talent_scout"]

    assert len(talent_configs) == len(EXPECTED_TALENT_SCOUT_SOURCE_IDS)

    allowed_capture_modes = {"structured", "semi_structured", "evidence_only"}
    allowed_fallback_modes = {"structured", "semi_structured", "evidence_only"}
    allowed_crawler_classes = {
        "competition_source",
        "paper_author_source",
        "github_talent_source",
        "evidence_only_source",
    }
    allowed_entity_families = {
        "competition",
        "paper_author",
        "github_talent",
    }

    for cfg in talent_configs:
        assert cfg.get("is_enabled") is False
        assert cfg.get("crawler_class") in allowed_crawler_classes
        assert cfg.get("entity_family") in allowed_entity_families
        assert cfg.get("capture_mode") in allowed_capture_modes
        assert cfg.get("fallback_mode") in allowed_fallback_modes
        assert isinstance(cfg.get("sheet_name"), str) and cfg["sheet_name"].strip()
        assert len(cfg["sheet_name"]) <= 31
        assert isinstance(cfg.get("tracks"), list)
        assert isinstance(cfg.get("requires_auth"), bool)
        assert isinstance(cfg.get("adapter_key"), str) and cfg["adapter_key"].strip()
        assert isinstance(cfg.get("seed_urls"), list) and cfg["seed_urls"]
        assert isinstance(cfg.get("name"), str) and cfg["name"].strip()
        assert cfg.get("schedule") == "daily"


def test_talent_scout_sources_wire_excellent_capabilities():
    configs = load_all_source_configs()
    talent_configs = {
        cfg["id"]: cfg for cfg in configs if cfg.get("dimension") == "talent_scout"
    }

    openreview = talent_configs["openreview_author"]
    assert openreview["crawler_class"] == "paper_author_source"
    assert openreview["capture_mode"] == "structured"
    assert openreview["adapter_key"] == "openreview_notes"
    assert openreview["openreview_group_id"] == "ICLR.cc/2026/Conference"

    academic = talent_configs["academic_paper_authors"]
    assert academic["crawler_class"] == "paper_author_source"
    assert academic["adapter_key"] == "author_aggregate_json"
    assert academic["local_results_path"] == "excellent_20260425/academic_papers/results.json"

    github = talent_configs["github_ai_repo_contributors"]
    assert github["adapter_key"] == "github_contributors"
    assert github.get("repo_seeds") in (None, [])
    assert github["topics"] == [
        "llm",
        "machine-learning",
        "deep-learning",
        "nlp",
        "reinforcement-learning",
        "autonomous-agents",
    ]
    assert github["search_query"] == "stars:>1000 pushed:>2023-01-01"
    assert github["profile_enrichment"] is True
