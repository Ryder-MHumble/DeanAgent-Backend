"""全量爬取脚本 - 并行爬取所有启用的信源，实时进度条 + 完整报告。"""
import argparse
import asyncio
import logging
import sys
import time
import unicodedata
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Only configure logging when run as a script (not imported by pipeline)
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    # 只让脚本自身的输出可见，爬虫内部日志静默
    logging.getLogger("app").setLevel(logging.WARNING)

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


def _display_width(s: str) -> int:
    """计算字符串的终端显示宽度（CJK 字符占 2 列）"""
    return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in s)


def _ljust(s: str, width: int) -> str:
    return s + ' ' * max(0, width - _display_width(s))


def _rjust(s: str, width: int) -> str:
    return ' ' * max(0, width - _display_width(s)) + s


def _status_icon(status_value: str) -> str:
    return {
        "success": "🟢",
        "partial": "🟡",
        "no_new_content": "⚪",
        "failed": "🔴",
    }.get(status_value, "❓")


def _load_crawl_concurrency_config() -> dict[str, object]:
    """
    Load the crawl_concurrency.yaml configuration file.

    Returns a dict with concurrency settings. If the file doesn't exist,
    returns sensible defaults with both 'grouped' and 'fixed' strategies.

    Returns:
        dict: Configuration with structure like:
            {
                'strategy': 'grouped' or 'fixed',
                'grouped': {'static': 20, 'rss': 20, 'dynamic': 8, 'snapshot': 10},
                'fixed': {'default': 12}
            }
    """
    project_root = Path(__file__).resolve().parent.parent
    config_path = project_root / "app" / "config" / "crawl_concurrency.yaml"

    # Default configuration (fallback if file doesn't exist)
    defaults: dict[str, object] = {
        "strategy": "grouped",
        "grouped": {
            "static": 20,
            "rss": 20,
            "dynamic": 8,
            "snapshot": 10,
        },
        "fixed": {
            "default": 12,
        },
    }

    if not config_path.exists():
        return defaults

    try:
        with open(config_path, "r") as f:
            loaded = yaml.safe_load(f)
        if loaded and isinstance(loaded, dict):
            return loaded
    except Exception as exc:
        logging.warning(
            f"Failed to load crawl_concurrency.yaml from {config_path}: {exc}"
        )

    return defaults


def _group_configs_by_method(configs: list[dict]) -> dict[str, list[dict]]:
    """
    Group source configurations by their crawl_method field.

    Configs without a 'crawl_method' field default to 'static'.

    Args:
        configs: List of source configuration dicts

    Returns:
        dict: Grouped configs, e.g. {'static': [cfg1, cfg2], 'dynamic': [cfg3]}
    """
    grouped = {}
    for cfg in configs:
        method = cfg.get("crawl_method", "static")
        grouped.setdefault(method, []).append(cfg)
    return grouped


async def _run_grouped_concurrently(
    grouped: dict[str, list[dict]],
    concurrency_map: dict[str, int],
    pbar: object = None,
) -> list[dict]:
    """
    Run all crawl groups concurrently, with per-group concurrency control.

    This function orchestrates parallel execution of different crawl methods:
    - Each crawl method (static, dynamic, rss, snapshot) gets its own Semaphore
    - Within each group, tasks are limited by the concurrency value in concurrency_map
    - All groups run in parallel using asyncio.gather()
    - NOTE: Semaphore is bound per-method via default parameter to ensure proper isolation

    Args:
        grouped: Dict mapping crawl method to list of source configs
                 e.g. {'static': [cfg1, cfg2], 'dynamic': [cfg3], ...}
        concurrency_map: Dict mapping crawl method to max concurrent tasks
                        e.g. {'static': 20, 'dynamic': 8, 'snapshot': 10}
        pbar: Optional progress bar object (tqdm)

    Returns:
        list[dict]: Flattened list of crawl results from all groups
    """
    all_group_tasks = []

    for method, configs in grouped.items():
        # Get concurrency limit for this method, default to 5 if not specified
        max_concurrent = concurrency_map.get(method, 5)
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _crawl_with_semaphore(cfg, sem=semaphore):
            """Acquire semaphore, run crawl, then release.

            Note: sem is bound at definition time (default parameter) to ensure
            each iteration captures its own semaphore instance, not by reference.
            """
            async with sem:
                return await _crawl_single_source(cfg, pbar)

        # Create tasks for all configs in this group
        group_tasks = [_crawl_with_semaphore(cfg) for cfg in configs]

        # Schedule this group to run
        all_group_tasks.append(asyncio.gather(*group_tasks))

    # Run all groups in parallel and flatten results
    group_results = await asyncio.gather(*all_group_tasks)
    flattened = [result for group in group_results for result in group]

    return flattened


async def _crawl_single_source(config: dict, pbar=None) -> dict:
    """爬取单个信源并返回结果字典"""
    from app.crawlers.registry import CrawlerRegistry
    from app.crawlers.utils.json_storage import save_crawl_result_json

    source_id = config["id"]
    name = config.get("name", source_id)
    dim = config.get("dimension", "?")
    method = config.get("crawl_method", "?")

    try:
        crawler = CrawlerRegistry.create_crawler(config)
        result = await crawler.run()

        # 统计有内容的条目
        items_with_content = sum(
            1 for item in result.items if item.content
        )

        # 保存 JSON
        json_path = save_crawl_result_json(result, config)

        status_str = result.status.value

        if pbar:
            pbar.set_postfix_str(f"{dim}/{source_id[:20]}")
            pbar.update(1)

        return {
            "source_id": source_id,
            "name": name,
            "dimension": dim,
            "method": method,
            "status": status_str,
            "items_total": result.items_total,
            "items_with_content": items_with_content,
            "duration": result.duration_seconds,
            "error": result.error_message,
            "json_path": str(json_path) if json_path else None,
        }

    except Exception as exc:
        if pbar:
            pbar.update(1)
        return {
            "source_id": source_id,
            "name": name,
            "dimension": dim,
            "method": method,
            "status": "failed",
            "items_total": 0,
            "items_with_content": 0,
            "duration": 0,
            "error": str(exc),
            "json_path": None,
        }


async def run_all(
    dimension_filter: str | None = None,
    concurrency: int | None = None,
    strategy: str = "grouped",
):
    from app.crawlers.utils.playwright_pool import close_browser
    from app.scheduler.manager import load_all_source_configs

    configs = load_all_source_configs()

    # 只选启用的源
    enabled = [c for c in configs if c.get("is_enabled", True)]

    if dimension_filter:
        enabled = [c for c in enabled if c.get("dimension") == dimension_filter]

    if not enabled:
        print("没有找到匹配的启用信源。")
        if dimension_filter:
            dims = sorted({c.get("dimension", "?") for c in configs})
            print(f"可用维度: {', '.join(dims)}")
        return

    # Load concurrency configuration
    conc_config = _load_crawl_concurrency_config()

    # Determine execution strategy and concurrency settings
    concurrency_map: dict[str, int] | int
    if strategy == "grouped":
        concurrency_map = conc_config.get("strategies", {}).get("grouped", {
            "static": 20,
            "rss": 20,
            "dynamic": 8,
            "snapshot": 10,
        })
        if isinstance(concurrency_map, dict):
            strategy_desc = (
                f"分组 (static/rss={concurrency_map.get('static', 20)}, "
                f"dynamic={concurrency_map.get('dynamic', 8)}, "
                f"snapshot={concurrency_map.get('snapshot', 10)})"
            )
        else:
            strategy_desc = "分组 (默认)"
    else:  # fixed
        fixed_config = conc_config.get("strategies", {}).get("fixed", {})
        conc_val = concurrency or fixed_config.get("default", 5)
        concurrency_map = conc_val
        strategy_desc = f"固定 (并发={conc_val})"

    # 按维度分组统计
    dim_groups: dict[str, list[dict]] = {}
    for c in enabled:
        dim = c.get("dimension", "unknown")
        dim_groups.setdefault(dim, []).append(c)

    total = len(enabled)
    print("=" * 70)
    print(f"  全量爬取 — 共 {total} 个启用信源，{len(dim_groups)} 个维度")
    print(f"  策略: {strategy_desc}")
    print("=" * 70)
    for dim, sources in sorted(dim_groups.items()):
        print(f"  {dim}: {len(sources)} 源")
    print("=" * 70)
    print()

    # 爬取结果收集
    results: list[dict] = []
    global_start = time.time()

    # 创建进度条
    if HAS_TQDM:
        pbar = tqdm(total=total, desc="爬取进度", unit="源", ncols=80)
    else:
        pbar = None
        print(f"开始爬取 {total} 个信源...")

    # 并发爬取 - 根据策略选择执行方式
    if strategy == "grouped":
        grouped = _group_configs_by_method(enabled)
        assert isinstance(concurrency_map, dict)
        results = await _run_grouped_concurrently(grouped, concurrency_map, pbar)
    else:  # fixed
        assert isinstance(concurrency_map, int)
        semaphore = asyncio.Semaphore(concurrency_map)

        async def _crawl_with_semaphore(cfg):
            async with semaphore:
                return await _crawl_single_source(cfg, pbar)

        tasks = [_crawl_with_semaphore(cfg) for cfg in enabled]
        results = await asyncio.gather(*tasks)

    if pbar:
        pbar.close()

    # 关闭 Playwright（如果有 dynamic 源启动了它）
    try:
        await close_browser()
    except Exception:
        pass

    total_duration = time.time() - global_start

    # ━━━ 汇总报告 ━━━
    print()
    print("=" * 70)
    print("  爬取汇总")
    print("=" * 70)

    # 按维度汇总
    dim_summary: dict[str, dict] = {}
    for r in results:
        dim = r["dimension"]
        ds = dim_summary.setdefault(dim, {
            "total": 0, "success": 0, "failed": 0,
            "items": 0, "content": 0,
        })
        ds["total"] += 1
        if r["status"] in ("success", "no_new_content"):
            ds["success"] += 1
        else:
            ds["failed"] += 1
        ds["items"] += r["items_total"]
        ds["content"] += r["items_with_content"]

    # 列宽定义
    W_DIM, W_N, W_ITEM = 18, 6, 8
    sep_width = W_DIM + W_N * 2 + W_ITEM * 2 + 4  # 4 个列间空格

    print()
    print(
        f"{_ljust('维度', W_DIM)} "
        f"{_rjust('成功', W_N)} {_rjust('失败', W_N)} "
        f"{_rjust('条目', W_ITEM)} {_rjust('有内容', W_ITEM)}"
    )
    print("─" * sep_width)
    for dim in sorted(dim_summary):
        ds = dim_summary[dim]
        print(
            f"{_ljust(dim, W_DIM)} "
            f"{ds['success']:>{W_N}} {ds['failed']:>{W_N}} "
            f"{ds['items']:>{W_ITEM}} {ds['content']:>{W_ITEM}}"
        )
    total_items = sum(r["items_total"] for r in results)
    total_content = sum(r["items_with_content"] for r in results)
    total_success = sum(
        1 for r in results if r["status"] in ("success", "no_new_content")
    )
    total_failed = sum(
        1 for r in results if r["status"] not in ("success", "no_new_content")
    )
    print("─" * sep_width)
    print(
        f"{_ljust('合计', W_DIM)} "
        f"{total_success:>{W_N}} {total_failed:>{W_N}} "
        f"{total_items:>{W_ITEM}} {total_content:>{W_ITEM}}"
    )

    # 失败列表
    failed = [
        r for r in results if r["status"] not in ("success", "no_new_content")
    ]
    if failed:
        print(f"\n🔴 失败信源 ({len(failed)}):")
        for r in failed:
            err = (r["error"] or "unknown")[:80]
            print(f"  - {r['dimension']}/{r['source_id']}: {err}")

    # 零条目列表
    empty = [
        r for r in results
        if r["status"] in ("success", "no_new_content") and r["items_total"] == 0
    ]
    if empty:
        print(f"\n⚪ 成功但零条目 ({len(empty)}):")
        for r in empty:
            print(f"  - {r['dimension']}/{r['source_id']}")

    print(f"\n总耗时: {total_duration:.0f}s ({total_duration/60:.1f}min)")
    print()

    content_rate = (total_content / total_items * 100) if total_items else 0
    print(
        f"数据质量: {total_items} 条目, {total_content} 有内容 ({content_rate:.0f}%)"
    )

    return {
        "total_sources": total,
        "success": total_success,
        "failed": total_failed,
        "total_items": total_items,
        "total_with_content": total_content,
        "duration_seconds": round(total_duration, 1),
        "content_rate_pct": round(content_rate, 1),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="全量爬取所有启用的信源")
    parser.add_argument(
        "--dimension", "-d",
        help="只爬取指定维度 (如 technology, universities)",
    )
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        help="并发爬取数量 (仅在 --strategy fixed 时使用)",
    )
    parser.add_argument(
        "--strategy", "-s",
        choices=["grouped", "fixed"],
        default="grouped",
        help="执行策略: grouped (按方法分组) 或 fixed (固定并发) (默认 grouped)",
    )
    args = parser.parse_args()
    asyncio.run(run_all(
        dimension_filter=args.dimension,
        concurrency=args.concurrency,
        strategy=args.strategy,
    ))
