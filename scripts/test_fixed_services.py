#!/usr/bin/env python3
"""测试修复后的服务"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.db.client import init_client


async def test_services():
    """测试所有服务"""
    print("=" * 70)
    print("测试修复后的服务")
    print("=" * 70)
    print()

    # Initialize DB client
    await init_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    print("✓ 数据库客户端已初始化\n")

    # Test scholars
    try:
        from app.services.scholar._data import _load_all_raw
        scholars = _load_all_raw()
        print(f"✓ Scholars: {len(scholars)} 条记录")
        if scholars:
            print(f"  示例: {scholars[0].get('name', 'N/A')}")
    except Exception as e:
        print(f"✗ Scholars: {e}")

    # Test institutions
    try:
        from app.services.core.institution_service import get_institution_list
        result = get_institution_list(page=1, page_size=5)
        print(f"✓ Institutions: {result.total} 条记录")
        if result.items:
            print(f"  示例: {result.items[0].name}")
    except Exception as e:
        print(f"✗ Institutions: {e}")

    # Test projects
    try:
        from app.services.core.project_service import list_projects
        result = list_projects(page=1, page_size=5)
        print(f"✓ Projects: {result.total} 条记录")
        if result.items:
            print(f"  示例: {result.items[0].name}")
    except Exception as e:
        print(f"✗ Projects: {e}")

    # Test events
    try:
        from app.services.core.event_service import get_event_list
        result = get_event_list(page=1, page_size=5)
        print(f"✓ Events: {result.total} 条记录")
        if result.items:
            print(f"  示例: {result.items[0].title}")
    except Exception as e:
        print(f"✗ Events: {e}")

    print()
    print("=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_services())
