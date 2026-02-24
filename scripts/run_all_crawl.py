"""全量爬取脚本 - 遍历所有启用的信源，逐个爬取并输出进度和汇总。"""
import argparse
import asyncio
import logging
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# 只让脚本自身的输出可见，爬虫内部日志静默
logging.getLogger("app").setLevel(logging.WARNING)


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


async def run_all(
    dimension_filter: str | None = None,
    concurrency: int = 1,
):
    from app.crawlers.registry import CrawlerRegistry
    from app.crawlers.utils.json_storage import save_crawl_result_json
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

    # 按维度分组统计
    dim_groups: dict[str, list[dict]] = {}
    for c in enabled:
        dim = c.get("dimension", "unknown")
        dim_groups.setdefault(dim, []).append(c)

    total = len(enabled)
    print("=" * 70)
    print(f"  全量爬取 — 共 {total} 个启用信源，{len(dim_groups)} 个维度")
    print("=" * 70)
    for dim, sources in sorted(dim_groups.items()):
        names = ", ".join(s.get("name", s["id"]) for s in sources)
        print(f"  {dim} ({len(sources)}): {names}")
    print("=" * 70)
    print()

    # 爬取结果收集
    results: list[dict] = []
    global_start = time.time()

    for idx, config in enumerate(enabled, 1):
        source_id = config["id"]
        name = config.get("name", source_id)
        dim = config.get("dimension", "?")
        method = config.get("crawl_method", "?")

        header = f"[{idx}/{total}] {dim}/{source_id}"
        print(f"{header}  {name}  ({method})")
        print(f"{'─' * 60}")

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
            icon = _status_icon(status_str)

            print(
                f"  {icon} {status_str}  "
                f"条目: {result.items_total}  "
                f"有内容: {items_with_content}  "
                f"耗时: {result.duration_seconds:.1f}s"
            )
            if result.error_message:
                print(f"  ⚠️  {result.error_message[:120]}")
            if json_path:
                print(f"  📁 {json_path}")

            results.append({
                "source_id": source_id,
                "name": name,
                "dimension": dim,
                "method": method,
                "status": status_str,
                "items_total": result.items_total,
                "items_with_content": items_with_content,
                "duration": result.duration_seconds,
                "error": result.error_message,
            })

        except Exception as exc:
            print(f"  🔴 创建爬虫失败: {exc}")
            results.append({
                "source_id": source_id,
                "name": name,
                "dimension": dim,
                "method": method,
                "status": "failed",
                "items_total": 0,
                "items_with_content": 0,
                "duration": 0,
                "error": str(exc),
            })

        print()

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
    args = parser.parse_args()
    asyncio.run(run_all(dimension_filter=args.dimension))
