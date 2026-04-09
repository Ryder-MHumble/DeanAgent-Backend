from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.console_api.app import console_api_app
from app.services import console_service


def _iso(hours_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def _sample_calls() -> list[dict]:
    return [
        {
            "timestamp": _iso(1),
            "provider": "openrouter",
            "stage": "policy_tier1",
            "model": "openai/gpt-4o",
            "source_id": "policy_source",
            "input_tokens": 1000,
            "output_tokens": 500,
            "success": True,
            "provider_cost_usd": 0.2,
        },
        {
            "timestamp": _iso(2),
            "provider": "openrouter",
            "stage": "personnel_enrichment",
            "model": "google/gemini-2.5-flash",
            "source_id": "personnel_source",
            "input_tokens": 2000,
            "output_tokens": 1000,
            "success": True,
        },
        {
            "timestamp": _iso(3),
            "provider": "openrouter",
            "stage": "crawler_llm_faculty_detail",
            "model": "unknown/model-x",
            "source_id": "faculty_source",
            "input_tokens": 1200,
            "output_tokens": 800,
            "success": False,
        },
        {
            "timestamp": _iso(4),
            "provider": "openrouter",
            "stage": "crawler_scholar_fields",
            "model": "openai/gpt-4o",
            "source_id": "scholar_source",
            "input_tokens": 500,
            "output_tokens": 500,
            "success": True,
            "cost_usd": 0.05,
        },
        {
            "timestamp": _iso(5),
            "provider": "openrouter",
            "stage": "tech_frontier_topic",
            "model": "openai/gpt-4o",
            "source_id": "tech_source",
            "input_tokens": 1200,
            "output_tokens": 300,
            "success": True,
            "effective_cost_usd": 0.07,
            "cost_source": "pricing_map",
        },
        {
            "timestamp": _iso(6),
            "provider": "openrouter",
            "stage": "paper_transfer",
            "model": "unknown/model-y",
            "source_id": "paper_source",
            "input_tokens": 300,
            "output_tokens": 200,
            "success": True,
            "cost_source": "unpriced",
        },
        {
            "timestamp": _iso(1),
            "provider": "siliconflow",
            "stage": "policy_tier1",
            "model": "openai/gpt-4o",
            "source_id": "other_provider",
            "input_tokens": 999,
            "output_tokens": 111,
            "success": True,
            "cost_usd": 1.2,
        },
        {
            "timestamp": (datetime.now(timezone.utc) - timedelta(days=40)).isoformat(),
            "provider": "openrouter",
            "stage": "policy_tier2",
            "model": "openai/gpt-4o",
            "source_id": "old_record",
            "input_tokens": 400,
            "output_tokens": 400,
            "success": True,
            "cost_usd": 0.12,
        },
    ]


def _empty_workspace_rows(*, since: datetime) -> list[dict]:
    return []


def _empty_workspace_sources() -> list[dict]:
    return []


@pytest.mark.asyncio
async def test_get_console_api_usage_mixed_cost_and_module_mapping(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(console_service, "_load_llm_calls", _sample_calls)
    monkeypatch.setattr(console_service, "_load_workspace_api_rows", _empty_workspace_rows)
    monkeypatch.setattr(console_service, "_discover_workspace_api_sources", _empty_workspace_sources)

    result = await console_service.get_console_api_usage(days=7, limit=80)

    assert result.scope.provider == "openrouter"
    assert result.scope.system is None
    assert result.overview.total_calls == 6
    assert result.overview.priced_calls == 4
    assert result.overview.unpriced_calls == 2
    assert result.overview.unpriced_tokens == 2500
    assert result.overview.total_tokens == 9500
    assert result.overview.success_calls == 5
    assert result.overview.failed_calls == 1
    assert result.overview.success_rate == pytest.approx(83.33, abs=0.01)
    assert result.overview.total_cost_usd == pytest.approx(0.3209, abs=1e-6)
    assert result.overview.avg_cost_per_call_usd == pytest.approx(0.080225, abs=1e-6)

    module_map = {item.module: item for item in result.by_module}
    assert module_map["policy_intel"].call_count == 1
    assert module_map["personnel_intel"].call_count == 1
    assert module_map["crawler_faculty"].call_count == 1
    assert module_map["crawler_scholar"].call_count == 1
    assert module_map["tech_frontier"].call_count == 1
    assert module_map["paper_transfer"].call_count == 1

    assert sum(item.call_count for item in result.by_module) == result.overview.total_calls
    assert sum(item.total_tokens for item in result.by_model) == result.overview.total_tokens
    assert result.by_system[0].system == "deanagent-backend"


@pytest.mark.asyncio
async def test_get_console_api_usage_filters_apply_to_overview_and_recent_calls(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(console_service, "_load_llm_calls", _sample_calls)
    monkeypatch.setattr(console_service, "_load_workspace_api_rows", _empty_workspace_rows)
    monkeypatch.setattr(console_service, "_discover_workspace_api_sources", _empty_workspace_sources)

    result = await console_service.get_console_api_usage(
        days=7,
        module="crawler_faculty",
        stage="crawler_llm_faculty_detail",
        model="unknown/model-x",
        source_id="faculty_source",
        success="failed",
        limit=5,
    )

    assert result.scope.module == "crawler_faculty"
    assert result.scope.stage == "crawler_llm_faculty_detail"
    assert result.scope.model == "unknown/model-x"
    assert result.scope.source_id == "faculty_source"
    assert result.scope.success == "failed"
    assert result.overview.total_calls == 1
    assert result.overview.failed_calls == 1
    assert result.overview.priced_calls == 0
    assert result.overview.unpriced_calls == 1
    assert len(result.recent_calls) == 1
    assert result.recent_calls[0].stage == "crawler_llm_faculty_detail"


@pytest.mark.asyncio
async def test_get_console_api_usage_limit_only_affects_recent_calls(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(console_service, "_load_llm_calls", _sample_calls)
    monkeypatch.setattr(console_service, "_load_workspace_api_rows", _empty_workspace_rows)
    monkeypatch.setattr(console_service, "_discover_workspace_api_sources", _empty_workspace_sources)

    result = await console_service.get_console_api_usage(days=7, limit=1)

    assert result.overview.total_calls == 6
    assert len(result.recent_calls) == 1
    assert result.scope.limit == 1


@pytest.mark.asyncio
async def test_get_console_api_usage_includes_workspace_systems(monkeypatch: pytest.MonkeyPatch):
    now = datetime.now(timezone.utc)

    def _backend_rows(*, since: datetime) -> list[dict]:
        return [
            {
                "timestamp": now - timedelta(hours=1),
                "provider": "openrouter",
                "system": "deanagent-backend",
                "system_label": "Crawler System",
                "module": "policy_intel",
                "stage": "policy_tier1",
                "model": "openai/gpt-4o",
                "source_id": "policy_source",
                "article_id": None,
                "article_title": None,
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "effective_cost_usd": 0.001,
                "cost_source": "provider",
                "success": True,
                "duration_ms": 420,
            }
        ]

    def _workspace_rows(*, since: datetime) -> list[dict]:
        return [
            {
                "timestamp": now - timedelta(hours=2),
                "provider": "openrouter",
                "system": "nano-bot",
                "system_label": "Nano Bot",
                "module": "nano_bot",
                "stage": "nanobot_chat",
                "model": "anthropic/claude-haiku-4.5",
                "source_id": "dingtalk",
                "article_id": None,
                "article_title": None,
                "input_tokens": 200,
                "output_tokens": 80,
                "total_tokens": 280,
                "effective_cost_usd": 0.002,
                "cost_source": "recorded",
                "success": True,
                "duration_ms": None,
            },
            {
                "timestamp": now - timedelta(hours=3),
                "provider": "openrouter",
                "system": "doc2brief",
                "system_label": "Doc2Brief",
                "module": "doc2brief",
                "stage": "doc2brief_openrouter_proxy",
                "model": "minimax/minimax-m2.7-20260318",
                "source_id": "rpt_001",
                "article_id": "rpt_001",
                "article_title": None,
                "input_tokens": 300,
                "output_tokens": 120,
                "total_tokens": 420,
                "effective_cost_usd": 0.003,
                "cost_source": "provider",
                "success": False,
                "duration_ms": 1800,
            },
        ]

    def _workspace_sources() -> list[dict]:
        return [
            {
                "kind": "nanobot_usage_jsonl",
                "path": Path("/tmp/nanobot.jsonl"),
                "system": "nano-bot",
                "system_label": "Nano Bot",
                "module": "nano_bot",
                "stage": "nanobot_chat",
            },
            {
                "kind": "openrouter_usage_ndjson",
                "path": Path("/tmp/doc2brief.ndjson"),
                "system": "doc2brief",
                "system_label": "Doc2Brief",
                "module": "doc2brief",
                "stage": "doc2brief_openrouter_proxy",
            },
            {
                "kind": "openrouter_usage_ndjson",
                "path": Path("/tmp/fronted.ndjson"),
                "system": "dean-agent-fronted",
                "system_label": "Dean Agent Fronted",
                "module": "dean_fronted",
                "stage": "dean_fronted_openrouter_proxy",
            },
        ]

    monkeypatch.setattr(console_service, "_load_backend_api_rows", _backend_rows)
    monkeypatch.setattr(console_service, "_load_workspace_api_rows", _workspace_rows)
    monkeypatch.setattr(console_service, "_discover_workspace_api_sources", _workspace_sources)

    result = await console_service.get_console_api_usage(days=7, limit=20)

    systems = {item.system: item for item in result.by_system}
    assert systems["deanagent-backend"].call_count == 1
    assert systems["nano-bot"].call_count == 1
    assert systems["doc2brief"].call_count == 1
    assert systems["dean-agent-fronted"].call_count == 0

    assert result.overview.total_calls == 3
    assert len(result.trend_series) == 4
    assert result.available_filters.systems == sorted([
        "deanagent-backend",
        "nano-bot",
        "doc2brief",
        "dean-agent-fronted",
    ])



def test_console_api_usage_endpoint_defaults_and_response_shape(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(console_service, "_load_llm_calls", _sample_calls)
    monkeypatch.setattr(console_service, "_load_workspace_api_rows", _empty_workspace_rows)
    monkeypatch.setattr(console_service, "_discover_workspace_api_sources", _empty_workspace_sources)

    client = TestClient(console_api_app)
    response = client.get("/api-monitor/usage")

    assert response.status_code == 200
    payload = response.json()

    assert payload["scope"]["provider"] == "openrouter"
    assert payload["scope"]["days"] == 7
    assert payload["scope"]["system"] is None
    assert payload["scope"]["limit"] == 80
    assert "overview" in payload
    assert "by_system" in payload
    assert "by_module" in payload
    assert "by_model" in payload
    assert "by_stage" in payload
    assert "trend_series" in payload
    assert "recent_calls" in payload
    assert "available_filters" in payload
    assert "systems" in payload["available_filters"]
    assert "generated_at" in payload
