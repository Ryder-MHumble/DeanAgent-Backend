#!/usr/bin/env python3
"""Generate consolidated API docs and machine-readable inventories.

Outputs:
  - docs/api/API_REFERENCE.md
  - docs/api/api_inventory.json
  - docs/api/source_inventory.json
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from app.api.deprecation import DEFAULT_SUNSET_DATE, get_replacement_map
from app.main import app

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs" / "api"
SOURCES_DIR = ROOT / "sources"
DEPRECATED_ROUTE_REPLACEMENTS = get_replacement_map()


def _collect_routes() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for route in app.routes:
        if not hasattr(route, "methods") or not hasattr(route, "path"):
            continue
        if not route.path.startswith("/api/v1"):
            continue
        methods = sorted(m for m in route.methods if m not in {"HEAD", "OPTIONS"})
        if not methods:
            continue
        path = route.path
        parts = [p for p in path.split("/") if p]
        service = parts[2] if len(parts) >= 3 else "unknown"
        if service == "intel" and len(parts) >= 4:
            service = f"intel/{parts[3]}"
        rows.append(
            {
                "methods": methods,
                "path": path,
                "service": service,
                "tags": list(getattr(route, "tags", []) or []),
                "summary": getattr(route, "summary", None),
                "name": getattr(route, "name", None),
                "deprecated": bool(getattr(route, "deprecated", False)),
            }
        )
    rows.sort(key=lambda x: (x["path"], x["methods"][0]))
    return rows


def _collect_sources() -> dict[str, Any]:
    all_sources: list[dict[str, Any]] = []
    file_stats: list[dict[str, Any]] = []

    for yaml_file in sorted(SOURCES_DIR.glob("*.yaml")):
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        dimension = data.get("dimension", yaml_file.stem)
        dimension_name = data.get("dimension_name")
        items = data.get("sources", []) or []
        enabled_count = sum(1 for item in items if item.get("is_enabled", True))
        file_stats.append(
            {
                "file": yaml_file.name,
                "dimension": dimension,
                "dimension_name": dimension_name,
                "total": len(items),
                "enabled": enabled_count,
            }
        )
        for item in items:
            merged = dict(item)
            merged.setdefault("dimension", dimension)
            merged.setdefault("dimension_name", dimension_name)
            merged["_file"] = yaml_file.name
            all_sources.append(merged)

    dim_total = Counter(str(item.get("dimension", "")) for item in all_sources)
    dim_enabled = Counter(
        str(item.get("dimension", "")) for item in all_sources if item.get("is_enabled", True)
    )
    group_counter = Counter(str(item.get("group", "")) for item in all_sources if item.get("group"))
    method_counter = Counter(
        str(item.get("crawl_method", "")) for item in all_sources if item.get("crawl_method")
    )
    tag_counter: Counter[str] = Counter()
    for item in all_sources:
        for tag in item.get("tags", []) or []:
            if tag:
                tag_counter[str(tag)] += 1

    dimensions = []
    for key, total in sorted(dim_total.items(), key=lambda x: (-x[1], x[0])):
        dim_name = next(
            (item.get("dimension_name") for item in all_sources if item.get("dimension") == key),
            None,
        )
        dimensions.append(
            {
                "key": key,
                "label": dim_name,
                "total": total,
                "enabled": dim_enabled[key],
            }
        )

    return {
        "total_sources": len(all_sources),
        "enabled_sources": sum(1 for item in all_sources if item.get("is_enabled", True)),
        "files": file_stats,
        "dimensions": dimensions,
        "top_groups": [{"key": k, "count": v} for k, v in group_counter.most_common(30)],
        "top_methods": [{"key": k, "count": v} for k, v in method_counter.most_common(20)],
        "top_tags": [{"key": k, "count": v} for k, v in tag_counter.most_common(40)],
    }


def _to_markdown(routes: list[dict[str, Any]], source_stats: dict[str, Any]) -> str:
    by_service: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_tag = Counter()
    method_counter = Counter()
    deprecated_routes: list[dict[str, Any]] = []
    for row in routes:
        by_service[row["service"]].append(row)
        for tag in row["tags"]:
            by_tag[tag] += 1
        for method in row["methods"]:
            method_counter[method] += 1
        if row.get("deprecated"):
            deprecated_routes.append(row)

    lines: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    lines.append("# API 参考总览")
    lines.append("")
    lines.append(f"- 生成时间（UTC）：`{now}`")
    lines.append(f"- API 路由总数：`{len(routes)}`")
    lines.append(
        "- Method 分布："
        + "、".join(f"`{m}` {c}" for m, c in sorted(method_counter.items(), key=lambda x: x[0]))
    )
    lines.append(f"- 信源总数：`{source_stats['total_sources']}`")
    lines.append(f"- 启用信源：`{source_stats['enabled_sources']}`")
    lines.append("")

    lines.append("## 服务清单")
    lines.append("")
    lines.append("| 服务 | 路由数 | 典型用途 |")
    lines.append("|---|---:|---|")
    for service, items in sorted(by_service.items(), key=lambda x: (-len(x[1]), x[0])):
        tags = sorted({tag for item in items for tag in item["tags"]})
        tag_hint = " / ".join(tags[:3]) if tags else "-"
        lines.append(f"| `{service}` | {len(items)} | {tag_hint} |")
    lines.append("")

    lines.append("## 信源维度覆盖")
    lines.append("")
    lines.append("| 维度 | 中文名 | 总数 | 启用 |")
    lines.append("|---|---|---:|---:|")
    for dim in source_stats["dimensions"]:
        lines.append(
            f"| `{dim['key']}` | {dim.get('label') or '-'} | {dim['total']} | {dim['enabled']} |"
        )
    lines.append("")

    lines.append("## 信源分组 TOP 20")
    lines.append("")
    lines.append("| group | 数量 |")
    lines.append("|---|---:|")
    for item in source_stats["top_groups"][:20]:
        lines.append(f"| `{item['key']}` | {item['count']} |")
    lines.append("")

    lines.append("## 信源标签 TOP 30")
    lines.append("")
    lines.append("| tag | 数量 |")
    lines.append("|---|---:|")
    for item in source_stats["top_tags"][:30]:
        lines.append(f"| `{item['key']}` | {item['count']} |")
    lines.append("")

    if deprecated_routes:
        lines.append("## Deprecated 路由")
        lines.append("")
        lines.append("| Method | 路径 | 替代接口 | Sunset |")
        lines.append("|---|---|---|---|")
        for row in sorted(deprecated_routes, key=lambda x: (x["path"], x["methods"][0])):
            methods = ",".join(row["methods"])
            replacement = DEPRECATED_ROUTE_REPLACEMENTS.get(row["path"], "-")
            lines.append(
                f"| `{methods}` | `{row['path']}` | "
                f"`{replacement}` | `{DEFAULT_SUNSET_DATE}` |"
            )
        lines.append("")

    lines.append("## Agent 调用快捷映射")
    lines.append("")
    lines.append("| 用户意图 | 推荐接口 | 参数建议 |")
    lines.append("|---|---|---|")
    lines.append(
        "| 快速看全部信源结构 | `GET /api/v1/sources/catalog` | "
        "`include_facets=true&page_size=200` |"
    )
    lines.append(
        "| 快速定位信源 ID | `GET /api/v1/sources/resolve` | "
        "`q=人社局` 或 `q=清华` |"
    )
    lines.append(
        "| 查询高校领导信源 | `GET /api/v1/sources/catalog` | "
        "`tag=leadership` 或 `group=university_leadership_official` |"
    )
    lines.append(
        "| 查询学者/师资信源 | `GET /api/v1/sources/catalog` | "
        "`dimension=scholars` 或 `tag=faculty` |"
    )
    lines.append(
        "| 按单个/多个信源直接拉取数据 | `GET /api/v1/sources/items` | "
        "`source_id=...` 或 `source_name=...`，配合 `page/page_size` 翻页 |"
    )
    lines.append(
        "| 按路径固定某个信源拉取数据 | `GET /api/v1/sources/{source_id}/items` | "
        "`date_from/date_to/keyword/page/page_size` |"
    )
    lines.append(
        "| 查询共建导师/两院关系学者 | `GET /api/v1/scholars` | "
        "`is_adjunct_supervisor=true` 或 `project_subcategory=兼职导师` |"
    )
    lines.append(
        "| 查询两院学生名单 | `GET /api/v1/students` | "
        "`institution=...`、`mentor_name=...`、`enrollment_year=...` |"
    )
    lines.append("")

    lines.append("## 路由明细")
    lines.append("")
    for service, items in sorted(by_service.items(), key=lambda x: x[0]):
        lines.append(f"### `{service}`")
        lines.append("")
        lines.append("| Method | Path | Tags | Summary |")
        lines.append("|---|---|---|---|")
        for item in sorted(items, key=lambda x: (x["path"], x["methods"][0])):
            methods = ",".join(item["methods"])
            tags = ",".join(item["tags"])
            summary = item.get("summary") or ""
            if item.get("deprecated"):
                summary = f"{summary}（deprecated）".strip()
            lines.append(f"| `{methods}` | `{item['path']}` | `{tags}` | {summary} |")
        lines.append("")

    lines.append("## 校验说明")
    lines.append("")
    lines.append("- 本文档由 `scripts/core/generate_api_docs.py` 自动生成。")
    lines.append(
        "- 若接口变更，请重新执行："
        "`./.venv/bin/python scripts/core/generate_api_docs.py`。"
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    routes = _collect_routes()
    source_stats = _collect_sources()
    markdown = _to_markdown(routes, source_stats)

    (DOCS_DIR / "API_REFERENCE.md").write_text(markdown, encoding="utf-8")

    with (DOCS_DIR / "api_inventory.json").open("w", encoding="utf-8") as f:
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "routes": routes,
        }
        json.dump(payload, f, ensure_ascii=False, indent=2)

    with (DOCS_DIR / "source_inventory.json").open("w", encoding="utf-8") as f:
        json.dump(
            {"generated_at": datetime.now(timezone.utc).isoformat(), **source_stats},
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"Generated {DOCS_DIR / 'API_REFERENCE.md'}")
    print(f"Generated {DOCS_DIR / 'api_inventory.json'}")
    print(f"Generated {DOCS_DIR / 'source_inventory.json'}")


if __name__ == "__main__":
    main()
