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

