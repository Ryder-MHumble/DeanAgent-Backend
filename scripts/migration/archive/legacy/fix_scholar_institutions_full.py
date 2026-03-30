#!/usr/bin/env python3
"""Comprehensive scholar institution cleanup.

Legacy scope script. Prefer:
  .venv/bin/python scripts/migration/fix_scholar_institutions.py --scope global [--apply]

Targets:
1) Normalize obvious university aliases (e.g. 清华 -> 清华大学, 北航 -> 北京航空航天大学)
2) Split concatenated university+department values into:
   - scholars.university: level-1 organization
   - scholars.department: level-2 department
3) Normalize CAS institute forms:
   - 中科院XX所 / 中国科学院XX所 -> 中国科学院大学 + XX研究所
4) Correct obvious region mislabels in institutions table
   - domestic+高校 rows that clearly match international university markers.

Usage:
  .venv/bin/python scripts/migration/archive/legacy/fix_scholar_institutions_full.py
  .venv/bin/python scripts/migration/archive/legacy/fix_scholar_institutions_full.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import re
import unicodedata
from collections import Counter

from app.config import settings
from app.db.pool import close_pool, get_pool, init_pool

EXACT_UNI_MAP = {
    "北航": "北京航空航天大学",
    "北航博士生": "北京航空航天大学",
    "北航教授": "北京航空航天大学",
    "北大": "北京大学",
    "清华": "清华大学",
    "北理工": "北京理工大学",
    "北邮": "北京邮电大学",
    "北交": "北京交通大学",
    "北师": "北京师范大学",
    "北科": "北京科技大学",
    "成电": "电子科技大学",
    "中科院": "中国科学院大学",
    "川大": "四川大学",
    "东大": "东南大学",
    "东南": "东南大学",
    "大连理工": "大连理工大学",
    "国防科学技术大学": "国防科技大学",
    "国防科大": "国防科技大学",
    "中科大": "中国科学技术大学",
    "上海交大": "上海交通大学",
    "上交大": "上海交通大学",
    "上交": "上海交通大学",
    "哈工大": "哈尔滨工业大学",
    "复旦": "复旦大学",
    "浙大": "浙江大学",
    "人大": "中国人民大学",
    "人民大学": "中国人民大学",
    "电子科大": "电子科技大学",
    "西安交大": "西安交通大学",
    "西工大": "西北工业大学",
    "西电": "西安电子科技大学",
    "武大": "武汉大学",
    "厦大": "厦门大学",
    "港科大": "香港科技大学",
    "港科": "香港科技大学",
    "港中文": "香港中文大学",
    "港中深": "香港中文大学(深圳)",
    "华科": "华中科技大学",
    "华东师范": "华东师范大学",
    "华东师大": "华东师范大学",
    "华南理工": "华南理工大学",
    "南京理工": "南京理工大学",
}

TRAILING_TITLE_RE = re.compile(
    r"(?:教授|副教授|讲师|博士生|博士|硕士生|硕士|本科生|研究生|phd)$",
    re.IGNORECASE,
)
INSTITUTION_END_RE = re.compile(
    r"(大学|学院|研究所|研究院|实验室|中心|Institute|University|College|Lab)$",
    re.IGNORECASE,
)
LEAD_SEP_RE = re.compile(r"^[\s,，;；:：|/\\\-—_()（）\[\]【】]+")
DEPT_HINT_RE = re.compile(
    r"(学院|学部|系|研究院|研究所|实验室|中心|研究中心|faculty|school|department|lab|institute|college)",
    re.IGNORECASE,
)
GENERIC_DEPT = {
    "学院",
    "学部",
    "系",
    "研究院",
    "研究所",
    "实验室",
    "中心",
    "研究中心",
}

CAMPUS_PREFIX = (
    "分校",
    "校区",
    "帕克分校",
    "厄巴纳",
    "洛杉矶分校",
    "圣地亚哥分校",
    "伯克利分校",
    "阿默斯特分校",
    "布法罗分校",
    "芝加哥分校",
    "圣克鲁斯分校",
    "默塞德分校",
    "戴维斯分校",
    "圣塔芭芭拉分校",
    "密西沙加分校",
    "(深圳)",
    "（深圳）",
    "深圳校区",
)

INTL_NAME_MARKERS = (
    "东京大学",
    "大阪大学",
    "京都大学",
    "哥伦比亚大学",
    "哈佛大学",
    "斯坦福大学",
    "范德比尔特大学",
    "佛罗里达大学",
    "多伦多大学",
    "曼彻斯特大学",
    "伯明翰大学",
    "牛津大学",
    "剑桥大学",
    "巴黎",
    "柏林",
    "慕尼黑",
    "苏黎世",
    "莫斯科",
    "新加坡国立大学",
    "南洋理工大学",
    "麻省理工学院",
    "耶鲁大学",
    "普林斯顿大学",
    "加州大学",
)


def clean_text(v: object) -> str:
    if v is None:
        return ""
    t = unicodedata.normalize("NFKC", str(v))
    t = t.replace("\u3000", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def norm_key(v: object) -> str:
    t = clean_text(v).lower()
    t = re.sub(r"[\s,，;；:：|/\\\-—_()（）\[\]【】'\"`·•.]+", "", t)
    return t


def clean_dept(v: object) -> str:
    t = clean_text(v)
    t = LEAD_SEP_RE.sub("", t)
    t = t.strip("，,;；:：|/\\-—_ ")
    return t


def dept_like(s: str) -> bool:
    s = clean_dept(s)
    if not s or s in GENERIC_DEPT or len(s) <= 2:
        return False
    return bool(DEPT_HINT_RE.search(s))


def merge_dept(old_dept: str, moved: str) -> str:
    o = clean_dept(old_dept)
    m = clean_dept(moved)
    if not m:
        return o
    if not o:
        return m
    if m in o:
        return o
    if o in m:
        return m
    return f"{o} / {m}"


def has_multi_affiliation_markers(uni: str) -> bool:
    markers = (";", "；", "|", " / ", "/", ",", "，")
    return any(x in uni for x in markers) and not uni.startswith("中国科学院")


def starts_with_campus_prefix(suffix: str) -> bool:
    if any(suffix.startswith(p) for p in CAMPUS_PREFIX):
        return True
    # Generic campus token, e.g. "欧文分校..."
    if re.match(r"^.{1,8}分校", suffix):
        return True
    return False


def should_apply_trimmed_uni(trimmed_uni: str) -> bool:
    if trimmed_uni in EXACT_UNI_MAP:
        return True
    if INSTITUTION_END_RE.search(trimmed_uni):
        return True
    return False


def build_like_clause(markers: tuple[str, ...], start_idx: int = 1) -> tuple[str, list[str]]:
    clauses: list[str] = []
    params: list[str] = []
    idx = start_idx
    for marker in markers:
        clauses.append(f"name ILIKE ${idx}")
        params.append(f"%{marker}%")
        idx += 1
    return " OR ".join(clauses), params


async def main(apply: bool) -> None:
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

    pool = get_pool()
    async with pool.acquire() as conn:
        org_rows = await conn.fetch(
            """
            SELECT name, COALESCE(org_type, '') AS org_type
            FROM institutions
            WHERE entity_type='organization' AND name IS NOT NULL AND BTRIM(name) <> ''
            """
        )
        org_name_to_type = {
            clean_text(r["name"]): clean_text(r["org_type"]) for r in org_rows
        }
        uni_orgs = [name for name, t in org_name_to_type.items() if t == "高校"]
        org_norm_map = {norm_key(name): name for name in uni_orgs}
        sorted_uni_orgs = sorted(
            set(uni_orgs),
            key=lambda s: len(norm_key(s)),
            reverse=True,
        )

        scholar_rows = await conn.fetch(
            """
            SELECT id, university, department
            FROM scholars
            """
        )

        updates: list[tuple[str, str, str]] = []
        reason_counter: Counter[str] = Counter()
        sample_changes: list[str] = []

        for row in scholar_rows:
            sid = str(row["id"])
            old_uni = clean_text(row["university"])
            old_dept = clean_dept(row["department"])
            if not old_uni:
                continue

            uni = old_uni
            dept = old_dept
            reasons: list[str] = []

            trimmed_uni = TRAILING_TITLE_RE.sub("", uni).strip(" ,，;；:：")
            if trimmed_uni != uni and should_apply_trimmed_uni(trimmed_uni):
                uni = trimmed_uni
                reasons.append("trim_title")

            if uni in EXACT_UNI_MAP:
                uni = EXACT_UNI_MAP[uni]
                reasons.append("alias_exact")

            cas_match = re.match(r"^(?:中国科学院|中科院)(.+?)(?:研究所|所)$", uni)
            if cas_match:
                body = clean_dept(cas_match.group(1))
                moved = body if body.endswith("研究所") else f"{body}研究所"
                dept = merge_dept(dept, moved)
                uni = "中国科学院大学"
                reasons.append("cas_institute_split")

            if not has_multi_affiliation_markers(uni):
                matched_org: str | None = None
                matched_suffix = ""
                for org in sorted_uni_orgs:
                    if not uni.startswith(org):
                        continue
                    if len(uni) <= len(org):
                        continue
                    suffix = clean_dept(uni[len(org) :])
                    if starts_with_campus_prefix(suffix):
                        continue
                    if dept_like(suffix):
                        matched_org = org
                        matched_suffix = suffix
                        break

                if matched_org:
                    uni = matched_org
                    dept = merge_dept(dept, matched_suffix)
                    reasons.append("prefix_split_dept")
                else:
                    m2 = re.match(r"^(.{2,60}?(?:大学|学院))(.+)$", uni)
                    if m2:
                        base = clean_text(m2.group(1))
                        suffix = clean_dept(m2.group(2))
                        if not starts_with_campus_prefix(suffix) and dept_like(suffix):
                            base_norm = norm_key(base)
                            if base_norm in org_norm_map:
                                uni = org_norm_map[base_norm]
                                dept = merge_dept(dept, suffix)
                                reasons.append("regex_split_known_org")

            new_uni = clean_text(uni)
            new_dept = clean_dept(dept)
            if new_uni == old_uni and new_dept == old_dept:
                continue

            updates.append((sid, new_uni, new_dept))
            reason_key = "+".join(sorted(set(reasons))) or "cleanup"
            reason_counter[reason_key] += 1
            if len(sample_changes) < 30:
                sample_changes.append(
                    f"[{sid}] {reason_key}\n"
                    f"  UNI: {old_uni} -> {new_uni}\n"
                    f"  DEP: {old_dept} -> {new_dept}"
                )

        print(f"scholar updates candidate: {len(updates)}")
        for reason, cnt in reason_counter.most_common(20):
            print(f"  {cnt:>4} | {reason}")
        print("\nSample changes:")
        for line in sample_changes:
            print(line)

        like_clause, like_params = build_like_clause(INTL_NAME_MARKERS)
        region_candidates = await conn.fetch(
            f"""
            SELECT id, name, region, org_type
            FROM institutions
            WHERE entity_type='organization'
              AND org_type='高校'
              AND region='国内'
              AND ({like_clause})
            ORDER BY name
            """,
            *like_params,
        )
        print(f"\nregion mislabel candidate rows: {len(region_candidates)}")
        for r in region_candidates[:30]:
            print(
                f"  {r['id']} | {r['name']} | {r['region']} -> 国际"
            )

        if not apply:
            return

        async with conn.transaction():
            for sid, new_uni, new_dept in updates:
                await conn.execute(
                    """
                    UPDATE scholars
                    SET university=$2, department=$3
                    WHERE id=$1
                    """,
                    sid,
                    new_uni or None,
                    new_dept or None,
                )

            if region_candidates:
                candidate_ids = [str(r["id"]) for r in region_candidates]
                await conn.execute(
                    """
                    UPDATE institutions
                    SET region='国际'
                    WHERE id = ANY($1::text[])
                    """,
                    candidate_ids,
                )

        print("\nAPPLY completed.")
        print(f"  scholars updated: {len(updates)}")
        print(f"  institutions region updated: {len(region_candidates)}")

    await close_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix scholar institution data.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to DB. Without this flag runs in dry-run mode.",
    )
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply))
