"""一次性脚本：修复 institutions 表的 type 和 category 字段。

参考业务方机构分类展示表。

用法：
  python scripts/fix_institution_categories.py --dry-run   # 预览
  python scripts/fix_institution_categories.py             # 执行
"""
from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# 精确名单（来自业务方分类表）
# ---------------------------------------------------------------------------

# 共建高校 - 示范性合作伙伴
_示范性合作伙伴 = {"清华大学", "北京大学"}

# 共建高校 - 京内高校
_京内高校 = {
    "中国科学院大学", "北京航空航天大学", "北京理工大学",
    "北京邮电大学", "北京师范大学", "中国人民大学",
}

# 共建高校 - 京外C9
_京外C9 = {
    "中国科学技术大学", "上海交通大学", "复旦大学", "浙江大学",
    "南京大学", "哈尔滨工业大学", "西安交通大学",
}

# 共建高校 - 综合强校
_综合强校 = {
    "同济大学", "华东师范大学", "东南大学",
    "南开大学", "天津大学", "山东大学",
    "中山大学", "厦门大学", "武汉大学", "吉林大学",
}

# 共建高校 - 工科强校
_工科强校 = {
    "西北工业大学", "西安电子科技大学", "华中科技大学",
    "电子科技大学", "南方科技大学",
}

# 共建高校 - 特色高校
_特色高校 = {"西湖大学"}

# 兄弟院校
_兄弟院校 = {"上海创智学院", "深圳河套学院"}

# 海外高校 - 香港高校（含澳门）
_香港高校_keywords = ["香港", "澳门"]

# 海外高校 - 亚太高校
_亚太高校_keywords = [
    "新加坡国立", "南洋理工", "早稻田", "昆士兰", "悉尼",
    "阿德莱德", "迪肯", "马来亚", "阿卜杜拉", "新西兰",
]

# 其他高校 - 特色专科学校
_特色专科学校 = {"中国政法大学", "中央民族大学", "中央财经大学"}

# 其他高校 - 北京市属高校
_北京市属高校 = {"首都师范大学", "北京体育大学", "北京舞蹈学院"}

# 其他高校 - 地方重点高校
_地方重点高校 = {
    "新疆大学", "青海大学", "深圳大学", "温州大学",
    "华南师范大学", "郑州师范学院", "山东建筑大学",
}

# 科研院所 - 同行业机构
_科研同行业_keywords = ["智源", "通用人工智能", "中国科学院"]

# 科研院所 - 国家实验室
_国家实验室_keywords = [
    "上海人工智能实验室", "上海AI Lab", "中关村", "昌平", "怀柔", "鹏城",
]

# 行业学会
_行业学会_keywords = ["学会"]

# ---------------------------------------------------------------------------
# type 推断
# ---------------------------------------------------------------------------

def _classify_type(name: str) -> str | None:
    """推断正确的 type。"""
    n = name.lower()

    # 行业学会
    if any(kw in name for kw in _行业学会_keywords):
        return "academic_society"

    # 企业
    if any(kw in n for kw in [
        "公司", "集团", "有限", "股份", "巴斯夫", "礼来",
        "meta ai", "huawei", "amazon", "google", "microsoft",
        "吉利", "银河通用", "亚马逊", "医疗ai科技",
    ]):
        if "大学" not in n:
            return "company"

    # 研究机构
    if any(kw in n for kw in [
        "研究院", "研究所", "研究中心", "实验室", "科学院",
        "自动化所", "计算所", "软件所", "医学科学院",
        "a*star", "cnrs", "inria", "max planck",
    ]):
        # 排除"中国科学院大学"（它是大学）
        if "大学" in name:
            return "university"
        return "research_institute"

    # 医院
    if "医院" in n:
        return "research_institute"

    # 高校
    if any(kw in n for kw in [
        "大学", "学院", "university", "college",
        "ucla", "usc", "mit", "caltech",
    ]):
        return "university"

    # 特殊
    if "ai lab" in n:
        return "research_institute"

    return None


# ---------------------------------------------------------------------------
# category 推断
# ---------------------------------------------------------------------------

def _classify_category(name: str, current_cat: str | None, inst_type: str) -> str | None:
    """推断 category。返回 None 表示不修改。"""
    # "综合高校" → "综合强校"（数据库旧值统一修正）
    if current_cat == "综合高校":
        return "综合强校"

    # 已有合理 category 的不覆盖，除非 type 变了导致 category 不匹配
    if current_cat and current_cat != "-":
        if inst_type != "university" and current_cat in (
            "京内高校", "京外C9", "综合高校", "综合强校", "工科强校", "特色高校",
            "示范性合作伙伴", "兄弟院校", "地方重点高校", "北京市属高校",
            "其他高校", "特色专科学校",
        ):
            pass  # type 变了，需要重新分类
        else:
            return None

    # --- 科研院所 ---
    if inst_type == "research_institute":
        for kw in _国家实验室_keywords:
            if kw in name:
                return "科研院所-国家实验室"
        for kw in _科研同行业_keywords:
            if kw in name:
                return "科研院所-同行业"
        if any(kw in name.lower() for kw in [
            "自动化", "计算", "软件", "信息", "人工智能", "智能",
            "自动化所", "a*star",
        ]):
            return "科研院所-同行业"
        return "科研院所-交叉学科"

    # --- 企业 ---
    if inst_type == "company":
        return None

    # --- 行业学会 ---
    if inst_type == "academic_society":
        return "行业学会"

    # --- 以下都是 university ---
    if inst_type != "university":
        return None

    # 1) 精确名单匹配（优先级最高）
    # 对于"XX大学YY学院"这种，先提取母校名
    base_name = name
    if "大学" in name and ("学院" in name or "系" in name):
        idx = name.index("大学") + 2
        base_name = name[:idx]

    if base_name in _示范性合作伙伴:
        return "示范性合作伙伴"
    if base_name in _京内高校:
        return "京内高校"
    if base_name in _京外C9:
        return "京外C9"
    if base_name in _综合强校 or name.startswith(tuple(_综合强校)):
        return "综合强校"
    if base_name in _工科强校:
        return "工科强校"
    if base_name in _特色高校:
        return "特色高校"
    if base_name in _兄弟院校 or name in _兄弟院校:
        return "兄弟院校"
    if base_name in _特色专科学校 or name in _特色专科学校:
        return "特色专科学校"
    if base_name in _北京市属高校 or name in _北京市属高校:
        return "北京市属高校"
    if base_name in _地方重点高校 or name in _地方重点高校:
        return "地方重点高校"

    # 哈工大分校跟随本部
    if "哈尔滨工业大学" in name:
        return "京外C9"
    # 国防科技大学、哈尔滨工程大学
    if name in {"国防科技大学", "哈尔滨工程大学"}:
        return "工科强校"
    # 宁波东方理工
    if name in {"宁波东方理工大学"}:
        return "特色高校"

    # 2) 香港/澳门高校
    if any(kw in name for kw in _香港高校_keywords):
        return "香港高校"

    # 3) 海外高校
    # 英文名
    intl_keywords = [
        "stanford", "ucla", "mit", "caltech", "cornell", "yale",
        "oxford", "cambridge", "eth", "epfl",
        "pittsburgh", "edinburgh", "imperial",
        "singapore", "nanyang", "kaist", "waseda", "tokyo",
        "queensland", "adelaide", "sydney", "melbourne", "deakin",
        "manchester", "liverpool", "leiden", "groningen", "ghent",
        "manitoba", "ottawa", "canterbury", "queen's belfast",
        "tubingen", "upsala", "umeå", "karlsruhe",
        "federico santa", "mary queen", "malaya", "vanderbilt",
    ]
    # 中文名海外大学
    overseas_cn = [
        "帝国理工", "牛津", "剑桥", "耶鲁", "康奈尔", "纽约大学",
        "斯坦福", "麻省理工", "苏黎世联邦", "瑞典皇家", "瑞士联邦",
        "新加坡国立", "南洋理工", "早稻田", "昆士兰", "悉尼",
        "阿德莱德", "迪肯", "曼尼托巴", "渥太华", "乌普萨拉",
        "于默奥", "卡尔斯鲁厄", "米兰理工", "图宾根", "格罗宁根",
        "莱顿", "贝尔法斯特", "费德里科", "利物浦", "伦敦",
        "比利时", "新西兰", "北卡罗来纳", "加州大学", "范德比尔特",
        "马来亚", "阿卜杜拉", "德蒙福特", "爱丁堡", "匹兹堡",
    ]

    n = name.lower()
    is_overseas = False
    if any(kw in n for kw in intl_keywords):
        is_overseas = True
    if any(kw in name for kw in overseas_cn):
        is_overseas = True

    if is_overseas:
        # 细分亚太/欧美
        if any(kw in name for kw in _亚太高校_keywords):
            return "亚太高校"
        return "欧美高校"

    # 纯英文名且没有中文 → 海外
    has_chinese = any('\u4e00' <= c <= '\u9fff' for c in name)
    if not has_chinese:
        return "欧美高校"

    # 4) 国内兜底
    # 中国农业大学等含"中国"的京内高校
    if name.startswith("中国农业大学"):
        return "京内高校"

    return "其他高校"


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

async def main(dry_run: bool = True):
    from app.db.client import init_client, get_client

    await init_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    cli = get_client()

    all_data = []
    offset = 0
    while True:
        r = (await cli.table("institutions")
             .select("id,name,type,category,priority")
             .range(offset, offset + 999)
             .execute())
        all_data.extend(r.data)
        if len(r.data) < 1000:
            break
        offset += 1000

    updates = []
    for inst in all_data:
        if inst["type"] == "department":
            continue

        name = inst["name"]
        old_type = inst["type"]
        old_cat = inst.get("category") or ""

        new_type = _classify_type(name) or old_type
        new_cat = _classify_category(name, old_cat if old_cat else None, new_type)

        changes: dict = {}
        if new_type != old_type:
            changes["type"] = new_type
        if new_cat and new_cat != old_cat:
            changes["category"] = new_cat

        if changes:
            updates.append((inst["id"], name, old_type, old_cat, changes))

    if not updates:
        print("No changes needed.")
        return

    print(f"{'[DRY RUN] ' if dry_run else ''}Changes to apply: {len(updates)}\n")

    # 按 group 分组显示
    for inst_id, name, old_type, old_cat, changes in sorted(updates, key=lambda x: x[1]):
        parts = []
        if "type" in changes:
            parts.append(f"type: {old_type} -> {changes['type']}")
        if "category" in changes:
            parts.append(f"cat: {old_cat or '-'} -> {changes['category']}")
        print(f"  {name:45s} {' | '.join(parts)}")

    if dry_run:
        print(f"\n[DRY RUN] Would update {len(updates)} institutions. "
              "Run without --dry-run to apply.")
        return

    for inst_id, name, _, _, changes in updates:
        await cli.table("institutions").update(changes).eq("id", inst_id).execute()

    print(f"\nUpdated {len(updates)} institutions.")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    asyncio.run(main(dry_run=dry))
