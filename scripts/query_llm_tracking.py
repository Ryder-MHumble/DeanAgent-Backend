#!/usr/bin/env python3
"""Simple script to query LLM API call tracking data locally.

Usage:
    python scripts/query_llm_tracking.py --summary                    # 总体统计
    python scripts/query_llm_tracking.py --stage policy_tier2         # 按阶段查询
    python scripts/query_llm_tracking.py --article {article_id}       # 按文章查询
    python scripts/query_llm_tracking.py --cost-by-model              # 成本分类
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import BASE_DIR


def load_summary() -> dict[str, Any]:
    """Load summary statistics."""
    summary_file = BASE_DIR / "data" / "logs" / "llm_calls" / "summary.json"
    if not summary_file.exists():
        return {}
    with open(summary_file) as f:
        return json.load(f)


def load_calls() -> list[dict[str, Any]]:
    """Load all call records from JSONL."""
    calls_file = BASE_DIR / "data" / "logs" / "llm_calls" / "calls.jsonl"
    if not calls_file.exists():
        return []
    calls = []
    with open(calls_file) as f:
        for line in f:
            if line.strip():
                calls.append(json.loads(line))
    return calls


def print_summary() -> None:
    """Print overall summary."""
    summary = load_summary()
    if not summary:
        print("No LLM tracking data found.")
        return

    print("\n" + "=" * 70)
    print("LLM API CALL TRACKING SUMMARY")
    print("=" * 70)

    print(f"\nTotal Calls: {summary.get('total_calls', 0):,}")
    print(f"Total Cost: ${summary.get('total_cost_usd', 0.0):.4f} USD")
    print(f"Last Updated: {summary.get('last_updated', 'N/A')}")

    print("\n" + "-" * 70)
    print("By Model:")
    print("-" * 70)

    for model, stats in summary.get("models", {}).items():
        success = stats.get("success_count", 0)
        error = stats.get("error_count", 0)
        total = success + error
        input_tokens = stats.get("total_input_tokens", 0)
        output_tokens = stats.get("total_output_tokens", 0)
        cost = stats.get("total_cost_usd", 0.0)

        print(f"\n{model}:")
        print(f"  Calls: {total} (Success: {success}, Error: {error})")
        print(f"  Tokens: {input_tokens:,} (input) + {output_tokens:,} (output)")
        print(f"  Cost: ${cost:.4f} USD (avg ${cost/total if total > 0 else 0:.6f}/call)")


def print_by_stage(stage: str) -> None:
    """Print calls for a specific stage."""
    calls = load_calls()
    stage_calls = [c for c in calls if c.get("stage") == stage]

    if not stage_calls:
        print(f"No calls found for stage: {stage}")
        return

    print(f"\n{stage.upper()} STAGE - {len(stage_calls)} CALLS")
    print("=" * 70)

    total_cost = 0.0
    success_count = 0
    for call in stage_calls:
        total_cost += call.get("cost_usd", 0.0)
        if call.get("success"):
            success_count += 1

    print(f"Total: {len(stage_calls)} calls")
    print(f"Success: {success_count}/{len(stage_calls)}")
    print(f"Total Cost: ${total_cost:.4f} USD")
    print(f"Avg Cost: ${total_cost / len(stage_calls):.6f} USD/call")

    # Show last 5 calls
    print("\nLast 5 calls:")
    for call in stage_calls[-5:]:
        status = "✓" if call.get("success") else "✗"
        print(
            f"  {status} {call.get('timestamp')[:19]} | "
            f"{call.get('article_id', '?')[:8]}... | "
            f"{call.get('input_tokens'):4d}→{call.get('output_tokens'):4d} tokens | "
            f"${call.get('cost_usd', 0):.6f}"
        )


def print_by_article(article_id: str) -> None:
    """Print calls for a specific article."""
    calls = load_calls()
    article_calls = [c for c in calls if c.get("article_id") == article_id]

    if not article_calls:
        print(f"No calls found for article: {article_id}")
        return

    print(f"\nARTICLE: {article_id}")
    print("=" * 70)
    title = article_calls[0].get("article_title", "Unknown")
    print(f"Title: {title[:60]}...")
    print(f"Source: {article_calls[0].get('source_id', '?')}")
    print(f"Dimension: {article_calls[0].get('dimension', '?')}")

    total_cost = sum(c.get("cost_usd", 0.0) for c in article_calls)
    print(f"\nProcessing Stages: {len(article_calls)}")
    print(f"Total Cost: ${total_cost:.4f} USD")

    print("\nDetailed Calls:")
    for call in article_calls:
        status = "✓" if call.get("success") else "✗"
        print(
            f"  {status} Stage: {call.get('stage'):<25} | "
            f"Tokens: {call.get('input_tokens'):4d}→{call.get('output_tokens'):4d} | "
            f"Cost: ${call.get('cost_usd', 0):.6f}"
        )


def print_cost_by_model() -> None:
    """Print cost breakdown by model."""
    calls = load_calls()
    if not calls:
        print("No LLM tracking data found.")
        return

    # Group by model
    by_model: dict[str, list[dict[str, Any]]] = {}
    for call in calls:
        model = call.get("model", "unknown")
        if model not in by_model:
            by_model[model] = []
        by_model[model].append(call)

    print("\nCOST BREAKDOWN BY MODEL")
    print("=" * 70)

    total_cost = sum(c.get("cost_usd", 0.0) for c in calls)

    for model in sorted(by_model.keys()):
        model_calls = by_model[model]
        model_cost = sum(c.get("cost_usd", 0.0) for c in model_calls)
        model_success = sum(1 for c in model_calls if c.get("success"))
        model_tokens = sum(
            c.get("input_tokens", 0) + c.get("output_tokens", 0)
            for c in model_calls
        )

        percentage = (model_cost / total_cost * 100) if total_cost > 0 else 0

        print(f"\n{model}")
        print(f"  Calls: {len(model_calls)} (Success: {model_success})")
        print(
            f"  Tokens: {model_tokens:,} "
            f"({model_tokens//len(model_calls) if model_calls else 0}/call avg)"
        )
        print(f"  Cost: ${model_cost:.4f} ({percentage:.1f}% of total)")
        print(f"  Avg: ${model_cost/len(model_calls):.6f} USD/call")


def main() -> None:
    parser = argparse.ArgumentParser(description="Query LLM API call tracking data")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--summary",
        action="store_true",
        help="Print overall summary",
    )
    group.add_argument(
        "--stage",
        metavar="STAGE",
        help="Show calls for specific pipeline stage",
    )
    group.add_argument(
        "--article",
        metavar="ARTICLE_ID",
        help="Show calls for specific article",
    )
    group.add_argument(
        "--cost-by-model",
        action="store_true",
        help="Show cost breakdown by model",
    )

    args = parser.parse_args()

    if args.summary:
        print_summary()
    elif args.stage:
        print_by_stage(args.stage)
    elif args.article:
        print_by_article(args.article)
    elif args.cost_by_model:
        print_cost_by_model()


if __name__ == "__main__":
    main()
