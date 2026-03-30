#!/usr/bin/env python3
"""Batch set specific scholars to project tag 教育培养-兼职导师.

Usage:
  ./.venv/bin/python scripts/migration/archive/oneoff/tag_named_scholars_as_adjunct_mentors.py --dry-run
  ./.venv/bin/python scripts/migration/archive/oneoff/tag_named_scholars_as_adjunct_mentors.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from app.config import settings
from app.db.pool import close_pool, get_pool, init_pool
from app.services.stores import scholar_annotation_store as annotation_store

TARGET_PROJECT_TAG: dict[str, str] = {
    "category": "教育培养",
    "subcategory": "兼职导师",
    "project_id": "",
    "project_title": "",
}
SYSTEM_UPDATED_BY = "system:named_adjunct_mentors_20260327"

TARGET_NAMES: list[str] = [
    "张送根",
    "刘萌",
    "吴郦军",
    "聂礼强",
    "卢宇",
    "余胜泉",
    "孙德晖",
    "王迪",
    "李伟欣",
    "王蕴红",
    "胡继峰",
    "张煦尧",
    "徐健",
    "何晖光",
    "向世明",
    "刘晟材",
    "张建国",
    "金鑫",
    "赵冬斌",
    "周宇",
    "高宸",
    "陈志波",
    "范玲玲",
    "温颖",
    "唐博",
    "唐珂",
    "宋丹丹",
    "张直政",
    "张长水",
    "徐丰力",
    "陈姚静",
    "王立志",
    "弋力",
    "曾毅",
    "张凌寒",
    "赵峰",
    "洪涛",
    "赵亚杰",
    "易鸣洋",
    "梁小丹",
    "操晓春",
    "虞鑫",
    "周文柏",
    "何向南",
    "侯廷军",
    "潘培辰",
    "刘文印",
    "童咏昕",
    "陈大卫",
    "郭天南",
    "张岳",
    "黄文炳",
    "许洪腾",
    "沈蔚然",
    "林衍凯",
    "董迪",
    "高跃",
    "庞珣",
    "张文涛",
    "祁琦",
    "陈旭",
    "刘勇",
    "赵鑫",
    "魏哲巍",
    "胡迪",
    "张骁",
    "严睿",
    "王卫宁",
    "刘建国",
    "夏彤",
    "宫辰",
    "杨懿梅",
    "何昌华",
    "马坚伟",
    "程健",
    "于静",
    "陈锐",
    "张辉帅",
    "刘滨",
    "刘偲",
    "陈则宇",
    "杨耀东",
    "马越",
    "王冉冉",
    "罗迪",
    "陈明辰",
    "高昂",
    "曾坚阳",
    "朱博南",
    "卢长征",
    "王耀君",
    "杨为",
    "张喆",
    "王斌举",
    "吴建鑫",
    "于超",
    "王井东",
    "李刚",
    "邵斌",
    "颜珂",
    "鄂海红",
    "刘知远",
    "杨成",
    "周建山",
    "林椿眄",
    "陈晨",
    "王钢",
    "曾宪琳",
    "邵江逸",
    "马骋",
    "陈峰",
    "崔世晟",
    "程俊",
    "梁夏",
    "常毅",
    "赵世振",
    "杨建磊",
    "王鹤",
    "邓方",
]


def clean(value: Any) -> str:
    return str(value or "").strip()


def n(value: Any) -> str:
    return "".join(clean(value).replace("\u3000", " ").split()).lower()


async def connect_pool() -> None:
    if settings.POSTGRES_DSN:
        await init_pool(dsn=settings.POSTGRES_DSN)
    else:
        await init_pool(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
        )


def build_update_payload(scholar_cols: set[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if "project_tags" in scholar_cols:
        payload["project_tags"] = [TARGET_PROJECT_TAG]
    if "project_category" in scholar_cols:
        payload["project_category"] = TARGET_PROJECT_TAG["category"]
    if "project_subcategory" in scholar_cols:
        payload["project_subcategory"] = TARGET_PROJECT_TAG["subcategory"]
    if "is_cobuild_scholar" in scholar_cols:
        payload["is_cobuild_scholar"] = True
    if "relation_updated_by" in scholar_cols:
        payload["relation_updated_by"] = SYSTEM_UPDATED_BY
    if "relation_updated_at" in scholar_cols:
        payload["relation_updated_at"] = "now()"
    if "updated_at" in scholar_cols:
        payload["updated_at"] = "now()"
    return payload


async def run(apply_changes: bool) -> None:
    await connect_pool()
    pool = get_pool()

    matched_scholars: list[dict[str, Any]] = []
    unresolved_names: list[str] = []
    ambiguous_names: list[str] = []
    rows_updated = 0

    async with pool.acquire() as conn:
        scholars = [
            dict(r)
            for r in await conn.fetch(
                """
                SELECT id, name, university, email
                FROM scholars
                """
            )
        ]
        scholar_cols = {
            str(r["column_name"])
            for r in await conn.fetch(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='scholars'
                """
            )
        }

        by_name: dict[str, list[dict[str, Any]]] = {}
        for scholar in scholars:
            by_name.setdefault(n(scholar.get("name")), []).append(scholar)

        for raw_name in TARGET_NAMES:
            key = n(raw_name)
            candidates = by_name.get(key, [])
            if not candidates:
                unresolved_names.append(raw_name)
                continue
            if len(candidates) > 1:
                ambiguous_names.append(raw_name)
            matched_scholars.extend(candidates)

        # Deduplicate by scholar id
        dedup: dict[str, dict[str, Any]] = {}
        for scholar in matched_scholars:
            dedup[clean(scholar.get("id"))] = scholar
        matched_scholars = list(dedup.values())

        update_payload = build_update_payload(scholar_cols)

        if apply_changes and matched_scholars and update_payload:
            for scholar in matched_scholars:
                scholar_id = clean(scholar.get("id"))
                set_parts: list[str] = []
                params: list[Any] = []
                idx = 1
                for key, value in update_payload.items():
                    if value == "now()":
                        set_parts.append(f"{key} = now()")
                        continue
                    params.append(value)
                    set_parts.append(f"{key} = ${idx}")
                    idx += 1
                params.append(scholar_id)
                await conn.execute(
                    f"UPDATE scholars SET {', '.join(set_parts)} WHERE id = ${idx}",
                    *params,
                )
                annotation_store.update_relation(
                    scholar_id,
                    {
                        "project_tags": [TARGET_PROJECT_TAG],
                        "is_cobuild_scholar": True,
                        "relation_updated_by": SYSTEM_UPDATED_BY,
                    },
                )
                rows_updated += 1

    print("")
    print("===== Named Scholar Adjunct Tag Sync =====")
    print(f"Mode: {'APPLY' if apply_changes else 'DRY-RUN'}")
    print(f"target_names: {len(TARGET_NAMES)}")
    print(f"matched_scholars: {len(matched_scholars)}")
    print(f"ambiguous_names: {len(ambiguous_names)}")
    print(f"unresolved_names: {len(unresolved_names)}")
    print(f"rows_updated: {rows_updated}")

    if ambiguous_names:
        print("ambiguous_name_list:")
        for name in ambiguous_names:
            print(f"  - {name}")

    if unresolved_names:
        print("unresolved_name_list:")
        for name in unresolved_names:
            print(f"  - {name}")

    await close_pool()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tag given scholars with 教育培养-兼职导师",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview only")
    mode.add_argument("--apply", action="store_true", help="Apply updates")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(run(apply_changes=bool(args.apply)))


if __name__ == "__main__":
    main()
