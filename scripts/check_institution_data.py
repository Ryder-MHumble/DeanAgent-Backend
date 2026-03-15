"""检查机构数据的分类字段分布和错误."""
import asyncio
import os
from pathlib import Path

# 加载环境变量
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()

from app.db.client import init_client, get_client


async def main():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        print("错误: 未找到 SUPABASE_URL 或 SUPABASE_KEY")
        return

    await init_client(url, key)
    client = get_client()

    # 查询所有机构的分类字段
    res = await client.table("institutions").select(
        "id,name,entity_type,region,org_type,classification,sub_classification,type,category"
    ).execute()

    institutions = res.data or []

    print(f"总机构数: {len(institutions)}\n")

    # 统计各字段的值分布
    print("=" * 80)
    print("entity_type 分布:")
    entity_types = {}
    for inst in institutions:
        et = inst.get("entity_type") or "NULL"
        entity_types[et] = entity_types.get(et, 0) + 1
    for k, v in sorted(entity_types.items()):
        print(f"  {k}: {v}")

    print("\n" + "=" * 80)
    print("region 分布:")
    regions = {}
    for inst in institutions:
        r = inst.get("region") or "NULL"
        regions[r] = regions.get(r, 0) + 1
    for k, v in sorted(regions.items()):
        print(f"  {k}: {v}")

    print("\n" + "=" * 80)
    print("org_type 分布:")
    org_types = {}
    for inst in institutions:
        ot = inst.get("org_type") or "NULL"
        org_types[ot] = org_types.get(ot, 0) + 1
    for k, v in sorted(org_types.items()):
        print(f"  {k}: {v}")

    print("\n" + "=" * 80)
    print("classification 分布:")
    classifications = {}
    for inst in institutions:
        c = inst.get("classification") or "NULL"
        classifications[c] = classifications.get(c, 0) + 1
    for k, v in sorted(classifications.items()):
        print(f"  {k}: {v}")

    print("\n" + "=" * 80)
    print("sub_classification 分布:")
    sub_classifications = {}
    for inst in institutions:
        sc = inst.get("sub_classification") or "NULL"
        sub_classifications[sc] = sub_classifications.get(sc, 0) + 1
    for k, v in sorted(sub_classifications.items()):
        print(f"  {k}: {v}")

    print("\n" + "=" * 80)
    print("旧字段 type 分布:")
    types = {}
    for inst in institutions:
        t = inst.get("type") or "NULL"
        types[t] = types.get(t, 0) + 1
    for k, v in sorted(types.items()):
        print(f"  {k}: {v}")

    print("\n" + "=" * 80)
    print("旧字段 category 分布:")
    categories = {}
    for inst in institutions:
        c = inst.get("category") or "NULL"
        categories[c] = categories.get(c, 0) + 1
    for k, v in sorted(categories.items()):
        print(f"  {k}: {v}")

    # 检查明显错误的数据：国际高校被标记为国内
    print("\n" + "=" * 80)
    print("检查明显错误的数据（国际高校被标记为国内）:")
    international_keywords = [
        "University", "Institute", "College", "MIT", "Stanford", "Harvard",
        "Berkeley", "Oxford", "Cambridge", "ETH", "EPFL", "NUS", "NTU",
        "帝国理工", "伦敦", "剑桥", "牛津", "苏黎世", "洛桑", "新加坡",
        "东京", "首尔", "悉尼", "墨尔本", "多伦多", "麦吉尔", "阿德莱德",
        "匹兹堡", "渥太华", "于默奥"
    ]

    wrong_region = []
    for inst in institutions:
        name = inst.get("name", "")
        region = inst.get("region")
        if region == "国内":
            for keyword in international_keywords:
                if keyword in name:
                    wrong_region.append({
                        "id": inst.get("id"),
                        "name": name,
                        "region": region,
                        "org_type": inst.get("org_type"),
                        "classification": inst.get("classification"),
                        "type": inst.get("type")
                    })
                    break

    if wrong_region:
        print(f"\n发现 {len(wrong_region)} 个可能错误的机构（国际高校被标记为国内）:")
        for inst in wrong_region:
            print(f"  - {inst['name']} (id={inst['id']}, region={inst['region']}, org_type={inst['org_type']}, type={inst['type']})")
    else:
        print("未发现明显错误")


if __name__ == "__main__":
    asyncio.run(main())
