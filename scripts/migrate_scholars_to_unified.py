#!/usr/bin/env python3
"""合并所有学者数据到统一的 scholars.json。

从各 data/scholars/**/latest.json 读取所有学者记录，
合并成单一扁平结构，写入 data/scholars/scholars.json。

字段处理：
- 删除：published_at, author, dimension, content_html, content_hash,
        is_new, source_id, source_url, crawled_at, first_seen_at,
        last_seen_at, is_active, data_completeness
- 保留：url_hash, url, content, tags + 所有 extra 字段（去掉上述 extra 中同名字段）
- 标准化：is_adjunct_supervisor (bool legacy) → adjunct_supervisor (dict)
- 去重：url_hash 相同时保留后出现的记录（手动维护优先级更高）

用法：
    python scripts/migrate_scholars_to_unified.py
    python scripts/migrate_scholars_to_unified.py --dry-run
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── 常量 ─────────────────────────────────────────────────────────────────────

SCHOLARS_DIR = Path("data/scholars")
OUTPUT_FILE = SCHOLARS_DIR / "scholars.json"

# 顶层字段里要删的（除了 extra，extra 单独处理）
_TOP_LEVEL_DROP = {
    "published_at", "author", "dimension", "content_html",
    "content_hash", "is_new", "source_id",
}

# extra 字段里要删的（爬虫元数据 + 数据质量）
_EXTRA_DROP = {
    "source_id", "source_url", "crawled_at",
    "first_seen_at", "last_seen_at", "is_active", "data_completeness",
}

_EMPTY_ADJUNCT: dict[str, str] = {
    "status": "", "type": "", "agreement_type": "",
    "agreement_period": "", "recommender": "",
}


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _normalize_adjunct(extra: dict) -> dict[str, str]:
    """标准化 adjunct_supervisor 字段：处理 legacy bool 和 dict 两种情况。"""
    # 新格式：adjunct_supervisor dict
    if "adjunct_supervisor" in extra and isinstance(extra["adjunct_supervisor"], dict):
        raw = extra["adjunct_supervisor"]
        return {
            "status": raw.get("status", ""),
            "type": raw.get("type", ""),
            "agreement_type": raw.get("agreement_type", ""),
            "agreement_period": raw.get("agreement_period", ""),
            "recommender": raw.get("recommender", ""),
        }
    # 旧格式：is_adjunct_supervisor bool
    if "is_adjunct_supervisor" in extra:
        if extra["is_adjunct_supervisor"] is True:
            return {**_EMPTY_ADJUNCT, "status": "已签署"}
    return dict(_EMPTY_ADJUNCT)


def _build_scholar_record(item: dict) -> dict | None:
    """从 CrawledItem 结构构建扁平 scholar 记录。返回 None 表示跳过。"""
    url_hash = item.get("url_hash", "").strip()
    if not url_hash:
        return None

    extra: dict = item.get("extra") or {}

    # 顶层保留字段
    record: dict = {
        "url_hash": url_hash,
        "url": item.get("url", ""),
        "content": item.get("content", "") or "",
        "tags": item.get("tags") or [],
    }

    # 合并 extra（去掉不需要的字段）
    for key, value in extra.items():
        if key in _EXTRA_DROP:
            continue
        if key in ("is_adjunct_supervisor", "adjunct_supervisor"):
            continue  # 单独处理
        record[key] = value

    # 标准化 adjunct_supervisor
    record["adjunct_supervisor"] = _normalize_adjunct(extra)

    return record


# ── 主流程 ────────────────────────────────────────────────────────────────────

def run(dry_run: bool = False) -> None:
    # 按文件路径排序；manual 目录最后处理，使手动数据优先级更高（覆盖同 hash 的爬虫数据）
    all_paths = sorted(
        glob.glob(str(SCHOLARS_DIR / "**" / "latest.json"), recursive=True),
        key=lambda p: ("manual" in p, p),  # manual 排最后
    )

    # 去除目标文件自身（如果已存在）
    all_paths = [p for p in all_paths if Path(p) != OUTPUT_FILE]

    print(f"找到 {len(all_paths)} 个数据文件")

    scholars_by_hash: dict[str, dict] = {}
    total_raw = 0
    skipped = 0

    for path in all_paths:
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  ⚠ 跳过 {path}: {exc}")
            skipped += 1
            continue

        items = payload.get("items", [])
        for item in items:
            total_raw += 1
            record = _build_scholar_record(item)
            if record is None:
                skipped += 1
                continue
            scholars_by_hash[record["url_hash"]] = record  # 后出现的覆盖先出现的

    scholars = list(scholars_by_hash.values())

    print(f"\n统计：")
    print(f"  原始条目总数：{total_raw}")
    print(f"  跳过/无效：{skipped}")
    print(f"  合并后学者数：{len(scholars)}（去重后）")

    # 按姓名排序，便于阅读
    scholars.sort(key=lambda s: s.get("name", ""))

    if dry_run:
        print(f"\n[DRY RUN] 前 3 条：")
        for s in scholars[:3]:
            print(f"  - {s.get('name')} ({s.get('university')}) hash={s.get('url_hash')[:12]}...")
        print(f"\n未写入文件（--dry-run 模式）")
        return

    output = {
        "last_updated": datetime.now(UTC).isoformat(),
        "scholars": scholars,
    }

    tmp = OUTPUT_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    tmp.replace(OUTPUT_FILE)

    size_kb = OUTPUT_FILE.stat().st_size // 1024
    print(f"\n✓ 写入 {OUTPUT_FILE}（{size_kb} KB）")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="合并学者数据到统一 scholars.json")
    parser.add_argument("--dry-run", action="store_true", help="预览，不写文件")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
