#!/usr/bin/env python3
"""
从共建高校信息汇总.xlsx 补充所有高校到 institutions.json
包括：基本信息 + AMiner org_name
"""
import json
import os
import sys
import time
from pathlib import Path

import httpx
import openpyxl
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

AMINER_API_KEY = os.getenv("AMINER_API_KEY")
AMINER_PERSON_SEARCH_URL = "https://datacenter.aminer.cn/gateway/open_platform/api/person/search"
INSTITUTIONS_FILE = Path("data/scholars/institutions.json")
EXCEL_FILE = Path("docs/共建高校信息汇总.xlsx")


def parse_multiline_field(text: str | None) -> list[str]:
    """解析多行文本字段"""
    if not text:
        return []
    return [line.strip() for line in str(text).split('\n') if line.strip()]


def parse_scholars(names: str | None, titles: str | None, departments: str | None,
                   research_areas: str | None) -> list[dict]:
    """解析学者信息"""
    name_list = parse_multiline_field(names)
    title_list = parse_multiline_field(titles)
    dept_list = parse_multiline_field(departments)
    research_list = parse_multiline_field(research_areas)

    max_len = max(len(name_list), len(title_list), len(dept_list), len(research_list))
    name_list += [''] * (max_len - len(name_list))
    title_list += [''] * (max_len - len(title_list))
    dept_list += [''] * (max_len - len(dept_list))
    research_list += [''] * (max_len - len(research_list))

    scholars = []
    for name, title, dept, research in zip(name_list, title_list, dept_list, research_list):
        if name:
            scholars.append({
                "name": name,
                "title": title or None,
                "department": dept or None,
                "research_area": research or None
            })

    return scholars


def generate_university_id(name: str) -> str:
    """生成高校 ID"""
    # 简单映射
    id_map = {
        "清华大学": "tsinghua",
        "北京大学": "pku",
        "上海交通大学": "sjtu",
        "中国人民大学": "ruc",
        "南京大学": "nju",
        "复旦大学": "fudan",
        "浙江大学": "zju",
        "中国科学技术大学": "ustc",
        "中国科学院": "cas",
        "中国科学院大学": "ucas",
        "北京航空航天大学": "buaa",
        "北京理工大学": "bit",
        "北京邮电大学": "bupt",
        "北京师范大学": "bnu",
        "南开大学": "nku",
        "天津大学": "tju",
        "哈尔滨工业大学": "hit",
        "吉林大学": "jlu",
        "同济大学": "tongji",
        "华东师范大学": "ecnu",
        "东南大学": "seu",
        "厦门大学": "xmu",
        "山东大学": "sdu",
        "武汉大学": "whu",
        "华中科技大学": "hust",
        "中山大学": "sysu",
        "西安交通大学": "xjtu",
        "西北工业大学": "nwpu",
        "西安电子科技大学": "xidian",
        "电子科技大学": "uestc",
        "南方科技大学": "sustech",
        "西湖大学": "westlake",
        "宁波东方理工大学": "oriteu",
        "香港大学": "hku",
        "香港中文大学": "cuhk",
        "香港科技大学": "hkust",
        "香港理工大学": "polyu",
        "香港城市大学": "cityu",
        "香港浸会大学": "hkbu",
        "新加坡国立大学": "nus",
        "南洋理工大学": "ntu",
    }
    return id_map.get(name, name.lower().replace(" ", "_"))


def search_scholar_to_get_org(scholar_name: str, univ_name: str, api_key: str) -> str | None:
    """通过搜索学者获取机构的 org_name"""
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json;charset=utf-8",
    }

    payload = {
        "name": scholar_name,
        "org": univ_name,
        "size": 5,
        "offset": 0,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                AMINER_PERSON_SEARCH_URL,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("success"):
                return None

            results = data.get("data", [])
            if not results:
                return None

            org_name = results[0].get("org", "")
            return org_name if org_name else None

    except Exception:
        return None


def parse_excel_universities() -> dict[str, dict]:
    """解析 Excel 文件，返回 {高校名: 详情数据}"""
    wb = openpyxl.load_workbook(EXCEL_FILE)
    ws = wb.active

    universities = {}
    for row in ws.iter_rows(min_row=7, values_only=True):
        if not row[2]:
            continue

        univ_name = str(row[2]).strip()

        # 跳过"总计"行
        if univ_name == "总计":
            continue

        data = {
            "category": row[1],
            "student_count_24": row[3] if isinstance(row[3], int) else None,
            "student_count_25": row[4] if isinstance(row[4], int) else None,
            "student_count_total": row[5] if isinstance(row[5], int) else None,
            "mentor_count": row[6] if isinstance(row[6], int) else None,
            "resident_leaders": parse_multiline_field(row[7]),
            "degree_committee": parse_multiline_field(row[8]),
            "teaching_committee": parse_multiline_field(row[9]),
            "mentor_info": {
                "name": row[10],
                "category": row[11],
                "department": row[12]
            } if row[10] else None,
            "university_leaders": parse_scholars(row[13], row[14], None, row[15]),
            "notable_scholars": parse_scholars(row[16], row[17], row[18], row[19]),
            "key_departments": parse_multiline_field(row[20]),
            "joint_labs": parse_multiline_field(row[21]),
            "training_cooperation": parse_multiline_field(row[22]),
            "academic_cooperation": parse_multiline_field(row[23]),
            "talent_dual_appointment": parse_multiline_field(row[24]),
            "recruitment_events": parse_multiline_field(row[25]),
            "visit_exchanges": parse_multiline_field(row[26]) if len(row) > 26 else [],
            "priority": row[27] if len(row) > 27 else None,
            "cooperation_focus": parse_multiline_field(row[28]) if len(row) > 28 else []
        }

        universities[univ_name] = data

    return universities


def main():
    if not AMINER_API_KEY:
        print("错误: 未找到 AMINER_API_KEY 环境变量")
        sys.exit(1)

    # 解析 Excel
    print("正在解析 Excel 文件...")
    excel_universities = parse_excel_universities()
    print(f"从 Excel 解析到 {len(excel_universities)} 所高校\n")

    # 读取现有 institutions.json
    if INSTITUTIONS_FILE.exists():
        with open(INSTITUTIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"last_updated": "", "universities": []}

    existing_universities = {u["id"]: u for u in data.get("universities", [])}

    # 处理每所高校
    new_count = 0
    updated_count = 0
    org_name_count = 0

    for i, (univ_name, details) in enumerate(sorted(excel_universities.items()), 1):
        univ_id = generate_university_id(univ_name)

        print(f"[{i}/{len(excel_universities)}] 处理 {univ_name} (ID: {univ_id})")

        # 检查是否已存在
        if univ_id in existing_universities:
            print(f"  ⊙ 已存在，更新详情数据")
            univ = existing_universities[univ_id]
            univ["details"] = details
            updated_count += 1
        else:
            print(f"  + 新增高校")
            univ = {
                "id": univ_id,
                "name": univ_name,
                "scholar_count": 0,
                "departments": [],
                "details": details
            }
            existing_universities[univ_id] = univ
            new_count += 1

        # 获取 org_name（如果还没有）
        if not univ.get("org_name"):
            # 尝试从 notable_scholars 中获取第一个学者
            notable_scholars = details.get("notable_scholars", [])
            if notable_scholars:
                scholar_name = notable_scholars[0].get("name")
                print(f"  → 搜索学者: {scholar_name}")

                org_name = search_scholar_to_get_org(scholar_name, univ_name, AMINER_API_KEY)
                if org_name:
                    univ["org_name"] = org_name
                    org_name_count += 1
                    print(f"  ✓ 找到 org_name: {org_name}")
                else:
                    print(f"  ⚠ 未找到 org_name")

                time.sleep(0.5)  # 避免 API 限流
            else:
                print(f"  ⚠ 没有学者信息，无法获取 org_name")
        else:
            print(f"  ⊙ 已有 org_name: {univ['org_name']}")

    # 更新数据
    from datetime import datetime, timezone
    data["universities"] = list(existing_universities.values())
    data["last_updated"] = datetime.now(timezone.utc).isoformat()

    # 写回文件
    with open(INSTITUTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✓ 处理完成")
    print(f"  - 新增高校: {new_count}")
    print(f"  - 更新高校: {updated_count}")
    print(f"  - 补充 org_name: {org_name_count}")
    print(f"  - 总高校数: {len(existing_universities)}")
    print(f"✓ 已更新 {INSTITUTIONS_FILE}")
    print(f"{'='*60}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ 用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
