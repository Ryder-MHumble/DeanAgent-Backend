"""Seed missing research institutes and industry associations into the institutions table."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from app.db.client import init_client, get_client


def _ri(id, name, org_name, category, priority=1):
    return {
        "id": id,
        "name": name,
        "org_name": org_name,
        "type": "research_institute",
        "entity_type": "organization",
        "region": "国内",
        "org_type": "研究机构",
        "category": category,
        "priority": priority,
    }


def _assoc(id, name, org_name, description="", priority=1):
    return {
        "id": id,
        "name": name,
        "org_name": org_name,
        "type": "academic_society",
        "entity_type": "organization",
        "region": "国内",
        "org_type": "行业学会",
        "priority": priority,
    }


INSTITUTIONS = [
    # ── 研究机构：同行业 ──────────────────────────────
    _ri("baai", "北京智源人工智能研究院",
        "Beijing Academy of Artificial Intelligence",
        "科研院所-同行业", priority=0),
    _ri("bigai", "北京通用人工智能研究院",
        "Beijing Institute for General Artificial Intelligence",
        "科研院所-同行业", priority=1),
    # ── 研究机构：交叉学科 ────────────────────────────
    _ri("smart_szbl", "深圳医学科学研究院&深圳湾实验室",
        "SMART / Shenzhen Bay Laboratory",
        "科研院所-交叉学科"),
    _ri("baqis", "北京量子信息科学研究院",
        "Beijing Academy of Quantum Information Sciences",
        "科研院所-交叉学科"),
    _ri("bimsa", "北京雁栖湖应用数学研究院",
        "Beijing Institute of Mathematical Sciences and Applications",
        "科研院所-交叉学科"),
    _ri("cibr", "北京脑科学与类脑研究所",
        "Chinese Institute for Brain Research",
        "科研院所-交叉学科"),
    # ── 研究机构：国家实验室 ──────────────────────────
    _ri("shlab", "上海人工智能实验室",
        "Shanghai Artificial Intelligence Laboratory",
        "科研院所-国家实验室", priority=0),
    _ri("znlab", "中关村实验室",
        "Zhongguancun Laboratory",
        "科研院所-国家实验室"),
    _ri("cplab", "昌平实验室",
        "Changping Laboratory",
        "科研院所-国家实验室"),
    _ri("hrlab", "怀柔实验室",
        "Huairou Laboratory",
        "科研院所-国家实验室"),
    _ri("pclab", "鹏城实验室",
        "Pengcheng Laboratory",
        "科研院所-国家实验室"),
    # ── 行业学会 ─────────────────────────────────────
    _assoc("ccf", "中国计算机学会",
           "China Computer Federation", priority=0),
    _assoc("caai", "中国人工智能学会",
           "Chinese Association for Artificial Intelligence", priority=0),
    _assoc("cips", "中国中文信息学会",
           "Chinese Information Processing Society of China"),
]


async def seed():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    await init_client(url, key)
    client = get_client()

    inserted = skipped = 0
    for inst in INSTITUTIONS:
        resp = await client.table("institutions").select("id").eq("id", inst["id"]).execute()
        if resp.data:
            print(f"  SKIP   {inst['id']} — already exists")
            skipped += 1
            continue
        await client.table("institutions").insert(inst).execute()
        print(f"  INSERT {inst['id']} — {inst['name']}")
        inserted += 1

    print(f"\nDone: {inserted} inserted, {skipped} skipped")


if __name__ == "__main__":
    asyncio.run(seed())
