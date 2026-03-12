"""Update institution categories and priorities in the DB.

按业务方需求，为现有机构设置规范化的 category（细粒度分类）和 priority（优先级）：

分类体系：
  共建高校
    - 示范性合作伙伴 (P0): 清华大学、北京大学
    - 京内高校       (P1): 中国科学院、中国人民大学
    - 京外C9         (P1): 上海交通大学、复旦大学、浙江大学、南京大学、中国科学技术大学

Usage:
    python scripts/update_institution_categories.py          # 实际更新
    python scripts/update_institution_categories.py --dry-run # 仅预览
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# 分类配置：institution_id → {category, priority}
# ---------------------------------------------------------------------------

# priority 在 DB 中存储为 smallint：0=P0, 1=P1, 2=P2, 3=P3
INSTITUTION_UPDATES: dict[str, dict] = {
    # 示范性合作伙伴（P0=0）：中关村人工智能研究院的核心战略合作高校
    "tsinghua": {"category": "示范性合作伙伴", "priority": 0},
    "pku":      {"category": "示范性合作伙伴", "priority": 0},

    # 京内高校（P1=1）：北京地区的重要合作高校
    "cas": {"category": "京内高校", "priority": 1},
    "ruc": {"category": "京内高校", "priority": 1},

    # 京外C9（P1=1）：C9 联盟中的非北京高校（沪浙宁）
    "sjtu":  {"category": "京外C9", "priority": 1},
    "fudan": {"category": "京外C9", "priority": 1},
    "zju":   {"category": "京外C9", "priority": 1},
    "nju":   {"category": "京外C9", "priority": 1},
    "ustc":  {"category": "京外C9", "priority": 1},
}


async def run(dry_run: bool = False) -> None:
    import os
    from app.db.client import init_client, get_client

    url = os.environ.get("SUPABASE_URL") or os.environ.get("SUPABASE_DB_URL", "")
    key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SECRET_KEY", "")
    if not url or not key:
        print("错误：未找到 SUPABASE_URL / SUPABASE_KEY 环境变量")
        sys.exit(1)

    await init_client(url, key)
    client = get_client()

    print(f"{'[DRY-RUN] ' if dry_run else ''}开始更新机构分类数据...\n")
    print(f"{'机构ID':<15} {'名称':<20} {'新 category':<20} {'新 priority'}")
    print("-" * 75)

    success = 0
    skipped = 0
    errors = 0

    for inst_id, updates in INSTITUTION_UPDATES.items():
        try:
            # 检查机构是否存在
            res = await client.table("institutions").select("id,name,category,priority").eq("id", inst_id).execute()
            rows = res.data or []

            if not rows:
                print(f"  ⚠  {inst_id:<13} — 不存在，跳过")
                skipped += 1
                continue

            row = rows[0]
            name = row.get("name", inst_id)
            old_cat = row.get("category") or "-"
            old_pri = row.get("priority")
            new_cat = updates["category"]
            new_pri = updates["priority"]
            # 格式化显示
            old_pri_str = f"P{old_pri}" if old_pri is not None else "-"
            new_pri_str = f"P{new_pri}"

            # 如果已经是目标值，跳过
            if old_cat == new_cat and old_pri == new_pri:
                print(f"  ✓  {inst_id:<13} {name:<18} 已是最新，跳过 ({new_cat} / {new_pri_str})")
                skipped += 1
                continue

            print(f"  →  {inst_id:<13} {name:<18} {old_cat} → {new_cat}   {old_pri_str} → {new_pri_str}")

            if not dry_run:
                await client.table("institutions").update(updates).eq("id", inst_id).execute()

            success += 1

        except Exception as exc:
            print(f"  ✗  {inst_id:<13} 更新失败: {exc}")
            errors += 1

    print("\n" + "=" * 75)
    print(f"完成：成功 {success} 条，跳过 {skipped} 条，失败 {errors} 条")
    if dry_run:
        print("（dry-run 模式，未实际写入）")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update institution categories in DB")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing to DB")
    args = parser.parse_args()

    # 加载 .env
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)

    asyncio.run(run(dry_run=args.dry_run))
