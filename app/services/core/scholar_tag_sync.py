"""Cross-entity synchronization helpers for scholar event/project tag fields."""
from __future__ import annotations

import logging
from typing import Any

from app.services.stores import scholar_annotation_store as annotation_store

logger = logging.getLogger(__name__)


def _get_client():
    from app.db.client import get_client  # noqa: PLC0415

    return get_client()


_SCHOLAR_COLUMNS_CACHE: set[str] | None = None


async def _get_scholar_columns() -> set[str]:
    global _SCHOLAR_COLUMNS_CACHE
    if _SCHOLAR_COLUMNS_CACHE is not None:
        return _SCHOLAR_COLUMNS_CACHE

    from app.db.pool import get_pool  # noqa: PLC0415

    rows = await get_pool().fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name='scholars'
        """,
    )
    _SCHOLAR_COLUMNS_CACHE = {str(r["column_name"]) for r in rows}
    return _SCHOLAR_COLUMNS_CACHE


def _uniq_ids(ids: list[str] | None) -> list[str]:
    if not ids:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for raw in ids:
        sid = str(raw or "").strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        out.append(sid)
    return out


async def _resolve_scholar_refs(
    refs: set[str],
    scholar_cols: set[str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Resolve external scholar refs to DB id and annotation key.

    - db id: scholars.id
    - annotation key: prefer scholars.url_hash when column exists, else scholars.id
    """
    if not refs:
        return {}, {}

    from app.db.pool import get_pool  # noqa: PLC0415

    has_url_hash = "url_hash" in scholar_cols
    select_cols = ["id"]
    if has_url_hash:
        select_cols.append("url_hash")

    sql = f"""
        SELECT {", ".join(select_cols)}
        FROM scholars
        WHERE id = ANY($1::text[])
    """
    if has_url_hash:
        sql += " OR url_hash = ANY($1::text[])"

    rows = [dict(r) for r in await get_pool().fetch(sql, sorted(refs))]

    ref_to_db_id: dict[str, str] = {}
    ref_to_annotation_key: dict[str, str] = {}
    for row in rows:
        scholar_id = str(row.get("id") or "").strip()
        scholar_url_hash = str(row.get("url_hash") or "").strip()
        annotation_key = scholar_url_hash or scholar_id
        if not scholar_id:
            continue

        aliases = {scholar_id}
        if scholar_url_hash:
            aliases.add(scholar_url_hash)

        for alias in aliases:
            if alias not in refs:
                continue
            ref_to_db_id[alias] = scholar_id
            ref_to_annotation_key[alias] = annotation_key

    # Keep unresolved refs as-is for annotation fallback updates.
    for ref in refs:
        ref_to_db_id.setdefault(ref, "")
        ref_to_annotation_key.setdefault(ref, ref)

    return ref_to_db_id, ref_to_annotation_key


def _normalize_project_tags(raw: Any) -> list[dict[str, str]]:
    tags: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return tags
    for item in raw:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "").strip()
        subcategory = str(item.get("subcategory") or "").strip()
        if not category and not subcategory:
            continue
        tags.append(
            {
                "category": category,
                "subcategory": subcategory,
                "project_id": str(item.get("project_id") or ""),
                "project_title": str(item.get("project_title") or ""),
            }
        )
    return tags


def _dedupe_project_tags(tags: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, str]] = []
    for tag in tags:
        key = (
            tag.get("category", ""),
            tag.get("subcategory", ""),
            tag.get("project_id", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(tag)
    return out


def _project_match(
    tag: dict[str, str],
    *,
    project_id: str,
    category: str,
    subcategory: str,
) -> bool:
    tag_pid = str(tag.get("project_id") or "")
    if tag_pid:
        return tag_pid == project_id
    return (
        str(tag.get("category") or "") == category
        and str(tag.get("subcategory") or "") == subcategory
    )


async def sync_event_scholar_memberships(
    *,
    event_id: str,
    new_scholar_ids: list[str] | None,
    old_scholar_ids: list[str] | None = None,
) -> None:
    """Synchronize scholars.participated_event_ids after event scholar_ids changes."""
    new_refs = set(_uniq_ids(new_scholar_ids))
    old_refs = set(_uniq_ids(old_scholar_ids))
    all_refs = new_refs | old_refs
    if not all_refs:
        return

    scholar_cols = await _get_scholar_columns()
    ref_to_db_id, ref_to_annotation_key = await _resolve_scholar_refs(
        all_refs,
        scholar_cols,
    )

    new_db_ids = {ref_to_db_id[r] for r in new_refs if ref_to_db_id.get(r)}
    old_db_ids = {ref_to_db_id[r] for r in old_refs if ref_to_db_id.get(r)}
    add_db_ids = new_db_ids - old_db_ids
    remove_db_ids = old_db_ids - new_db_ids
    target_db_ids = sorted(add_db_ids | remove_db_ids)

    new_keys = {ref_to_annotation_key[r] for r in new_refs}
    old_keys = {ref_to_annotation_key[r] for r in old_refs}
    add_keys = new_keys - old_keys
    remove_keys = old_keys - new_keys
    target_keys = sorted(add_keys | remove_keys)

    # 1) Persist to DB column when available.
    handled_annotation_keys: set[str] = set()
    if "participated_event_ids" in scholar_cols and target_db_ids:
        from app.db.pool import get_pool  # noqa: PLC0415

        client = _get_client()
        has_url_hash = "url_hash" in scholar_cols
        select_cols = ["id", "participated_event_ids"]
        if has_url_hash:
            select_cols.append("url_hash")
        rows = [
            dict(r)
            for r in await get_pool().fetch(
                f"""
                SELECT {", ".join(select_cols)}
                FROM scholars
                WHERE id = ANY($1::text[])
                """,
                target_db_ids,
            )
        ]
        by_id = {str(r.get("id")): r for r in rows}

        for scholar_id in target_db_ids:
            row = by_id.get(scholar_id) or {}
            current = _uniq_ids(row.get("participated_event_ids") or [])
            if scholar_id in add_db_ids and event_id not in current:
                current.append(event_id)
            if scholar_id in remove_db_ids:
                current = [eid for eid in current if eid != event_id]

            await (
                client.table("scholars")
                .update({"participated_event_ids": current})
                .eq("id", scholar_id)
                .execute()
            )

            annotation_key = str(row.get("url_hash") or scholar_id).strip()
            if annotation_key:
                annotation_store.update_relation(
                    annotation_key,
                    {"participated_event_ids": current},
                )
                handled_annotation_keys.add(annotation_key)

    # 2) Always maintain annotation overlay for schema-compat and fallback read paths.
    for key in target_keys:
        if not key or key in handled_annotation_keys:
            continue
        ann = annotation_store.get_annotation(key)
        current = _uniq_ids(ann.get("participated_event_ids") or [])
        if key in add_keys and event_id not in current:
            current.append(event_id)
        if key in remove_keys:
            current = [eid for eid in current if eid != event_id]
        try:
            annotation_store.update_relation(
                key,
                {"participated_event_ids": current},
            )
        except Exception as exc:
            logger.warning(
                "Failed to sync participated_event_ids annotation for %s: %s",
                key,
                exc,
            )


async def sync_project_scholar_memberships(
    *,
    project_id: str,
    project_title: str,
    category: str,
    subcategory: str,
    new_scholar_ids: list[str] | None,
    old_scholar_ids: list[str] | None = None,
) -> None:
    """Synchronize scholars.project_tags/is_cobuild_scholar when project-scholar links change."""
    new_ids = set(_uniq_ids(new_scholar_ids))
    old_ids = set(_uniq_ids(old_scholar_ids))
    add_ids = new_ids - old_ids
    remove_ids = old_ids - new_ids
    target_ids = sorted(add_ids | remove_ids)
    if not target_ids:
        return

    scholar_cols = await _get_scholar_columns()
    updatable_cols = {
        c
        for c in (
            "project_tags",
            "is_cobuild_scholar",
            "project_category",
            "project_subcategory",
        )
        if c in scholar_cols
    }
    if not updatable_cols:
        return

    select_cols = ["id"]
    if "project_tags" in scholar_cols:
        select_cols.append("project_tags")
    if "project_category" in scholar_cols:
        select_cols.append("project_category")
    if "project_subcategory" in scholar_cols:
        select_cols.append("project_subcategory")

    from app.db.pool import get_pool  # noqa: PLC0415

    client = _get_client()
    rows = [
        dict(r)
        for r in await get_pool().fetch(
            f"""
            SELECT {", ".join(select_cols)}
            FROM scholars
            WHERE id = ANY($1::text[])
            """,
            target_ids,
        )
    ]
    by_id = {str(r.get("id")): r for r in rows}

    for scholar_id in target_ids:
        row = by_id.get(scholar_id) or {"id": scholar_id}
        tags = _normalize_project_tags(row.get("project_tags") or [])

        # Backfill from legacy single-value fields when project_tags column is newly added.
        if not tags:
            legacy_category = str(row.get("project_category") or "").strip()
            legacy_subcategory = str(row.get("project_subcategory") or "").strip()
            if legacy_category or legacy_subcategory:
                tags = [
                    {
                        "category": legacy_category,
                        "subcategory": legacy_subcategory,
                        "project_id": "",
                        "project_title": "",
                    }
                ]

        if scholar_id in add_ids:
            tags = [
                t
                for t in tags
                if not _project_match(
                    t,
                    project_id=project_id,
                    category=category,
                    subcategory=subcategory,
                )
            ]
            tags.append(
                {
                    "category": category,
                    "subcategory": subcategory,
                    "project_id": project_id,
                    "project_title": project_title,
                }
            )
        if scholar_id in remove_ids:
            tags = [
                t
                for t in tags
                if not _project_match(
                    t,
                    project_id=project_id,
                    category=category,
                    subcategory=subcategory,
                )
            ]

        tags = _dedupe_project_tags(tags)
        first = tags[0] if tags else {}

        update_payload: dict[str, Any] = {}
        if "project_tags" in updatable_cols:
            update_payload["project_tags"] = tags
        if "is_cobuild_scholar" in updatable_cols:
            update_payload["is_cobuild_scholar"] = bool(tags)
        if "project_category" in updatable_cols:
            update_payload["project_category"] = str(first.get("category") or "")
        if "project_subcategory" in updatable_cols:
            update_payload["project_subcategory"] = str(first.get("subcategory") or "")

        if update_payload:
            await (
                client.table("scholars")
                .update(update_payload)
                .eq("id", scholar_id)
                .execute()
            )
