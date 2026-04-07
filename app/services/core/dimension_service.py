from __future__ import annotations

from app.services.stores.json_reader import get_dimension_stats

DIMENSION_NAMES = {
    "national_policy": "国家政策治理",
    "beijing_policy": "北京市政策治理",
    "technology": "技术前沿与创新",
    "talent": "人才与学术发展",
    "industry": "产业与投融资",
    "sentiment": "社交情报与舆情",
    "twitter": "社交媒体监测",
    "universities": "高校与科研生态",
    "events": "学术会议与活动",
    "personnel": "组织人事动态",
    "scholars": "学者与师资库",
}


async def list_dimensions() -> list[dict]:
    """List all dimensions with article counts and last updated timestamps."""
    stats = await get_dimension_stats()

    dimensions = []
    found = set()
    for dim_id, dim_stats in stats.items():
        found.add(dim_id)
        dimensions.append({
            "id": dim_id,
            "name": DIMENSION_NAMES.get(dim_id, dim_id),
            "article_count": dim_stats.get("total_items", 0),
            "last_updated": dim_stats.get("latest_crawl"),
        })

    # Include dimensions with zero articles
    for dim_id, dim_name in DIMENSION_NAMES.items():
        if dim_id not in found:
            dimensions.append({
                "id": dim_id,
                "name": dim_name,
                "article_count": 0,
                "last_updated": None,
            })

    dim_order = list(DIMENSION_NAMES.keys())
    return sorted(
        dimensions,
        key=lambda d: dim_order.index(d["id"]) if d["id"] in dim_order else len(dim_order),
    )
