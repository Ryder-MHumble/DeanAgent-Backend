"""把 adjunct_import/adjunct_supervisors/latest.json 中的学者按就职单位分发到各机构目录。

运行后会：
1. 按就职单位将学者写入 data/scholars/{group}/{group}_adjunct_faculty/latest.json
2. 把 adjunct_supervisor 关系字段写入 annotation store（防止爬虫覆盖）
3. 删除 data/scholars/adjunct_import/ 目录

用法：
  python scripts/data_import/redistribute_adjunct_scholars.py
  python scripts/data_import/redistribute_adjunct_scholars.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
SCHOLARS_DIR = ROOT / "data" / "scholars"
IMPORT_DIR = SCHOLARS_DIR / "adjunct_import" / "adjunct_supervisors"
ANNOTATIONS_FILE = ROOT / "data" / "state" / "scholar_annotations.json"

# ---------------------------------------------------------------------------
# University → group_id 映射
# ---------------------------------------------------------------------------

_UNI_GROUP: dict[str, str] = {
    "清华大学": "tsinghua",
    "清华大学深圳国际研究生院": "tsinghua",
    "北京大学": "pku",
    "中国人民大学": "ruc",
    "中国人民大学信息学院": "ruc",
    "上海交通大学": "sjtu",
    "浙江大学": "zju",
    "复旦大学": "fudan",
    "南京大学": "nju",
    "中国科学技术大学": "ustc",
    "北京理工大学": "bit",
    "北京理工大学自动化学院": "bit",
    "北京航空航天大学": "buaa",
    "北京航空航天大学计算机学院": "buaa",
    "北京邮电大学": "bupt",
    "北京师范大学": "bnu",
    "武汉大学": "whu",
    "南开大学": "nankai",
    "南开大学计算机学院": "nankai",
    "南开大学网络空间安全学院": "nankai",
    "哈尔滨工业大学": "hit",
    "哈尔滨工业大学（深圳）": "hit",
    "南方科技大学": "sustech",
    "中山大学": "sysu",
    "天津大学": "tju",
    "厦门大学": "xmu",
    "吉林大学": "jlu",
    "华南师范大学": "scnu",
    "深圳大学": "szu",
    "中央财经大学": "cufe",
    "中国政法大学": "cupl",
    "中央民族大学": "muc",
    "中国农业大学信息与电气工程学院": "cau",
    "山东建筑大学": "sdjzu",
    "山东第一医科大学附属肿瘤医院": "sdmu",
    "香港科技大学": "hkust",
    "西湖大学": "westlake",
    # 科研机构
    "中科院自动化所": "cas_ia",
    "中国科学院自动化所": "cas_ia",
    "中国科学院自动化研究所": "cas_ia",
    "中国科学院大学": "ucas",
    "中关村国家实验室": "cas_zgc_lab",
    "昌平国家实验室": "cpnl",
    "深圳湾实验室": "szbl",
    "深圳医学科学院": "smart",
    "上海AI Lab": "shailab",
    # 企业（归到 industry 组）
    "北京天智航医疗科技股份有限公司": "industry",
    "北京水木东方医用机器人技术创新中心有限公司": "industry",
    "北京银河通用机器人有限公司": "industry",
    "北京数巅科技有限公司": "industry",
}


def get_group(university: str) -> str:
    """Get group_id for a university, falling back to a slug of the name."""
    if university in _UNI_GROUP:
        return _UNI_GROUP[university]
    # Prefix match
    for uni, gid in _UNI_GROUP.items():
        if university.startswith(uni):
            return gid
    # Fallback: use first 4 chars as slug
    return "other"


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def redistribute(dry_run: bool) -> None:
    if not IMPORT_DIR.exists():
        logger.error("adjunct_import 目录不存在: %s", IMPORT_DIR)
        return

    with open(IMPORT_DIR / "latest.json", encoding="utf-8") as f:
        import_data = json.load(f)

    items = import_data.get("items", [])
    logger.info("读取到 %d 条待分发学者", len(items))

    # Group items by target (group_id, source_id)
    groups: dict[str, list[dict]] = {}
    for item in items:
        uni = item.get("extra", {}).get("university", "")
        group_id = get_group(uni)
        source_id = f"{group_id}_adjunct_faculty"
        key = f"{group_id}/{source_id}"
        groups.setdefault(key, []).append(item)

    logger.info("将分发到 %d 个机构目录", len(groups))

    # Load annotation store once
    annotations: dict = _load_json(ANNOTATIONS_FILE)
    now = datetime.now(UTC).isoformat()

    total_written = 0

    for key, group_items in sorted(groups.items()):
        group_id, source_id = key.split("/")
        target_dir = SCHOLARS_DIR / group_id / source_id
        target_file = target_dir / "latest.json"

        # Load existing file if present
        if target_file.exists():
            with open(target_file, encoding="utf-8") as f:
                existing = json.load(f)
            existing_hashes = {i["url_hash"] for i in existing.get("items", [])}
            existing_items = existing.get("items", [])
        else:
            existing_hashes = set()
            existing_items = []

        # Filter out duplicates
        new_items = [i for i in group_items if i["url_hash"] not in existing_hashes]
        all_items = existing_items + new_items
        total_written += len(new_items)

        uni_name = group_items[0]["extra"].get("university", group_id)
        logger.info(
            "  [%s] %s → %d 新增 / %d 已有  →  %s",
            group_id, uni_name, len(new_items), len(existing_items), target_file.relative_to(ROOT),
        )

        if not dry_run:
            payload = {
                "source_id": source_id,
                "source_name": f"{uni_name}兼职导师",
                "group": group_id,
                "crawled_at": now,
                "items": all_items,
            }
            _save_json(target_file, payload)

        # Write adjunct_supervisor to annotation store for each item
        for item in group_items:
            url_hash = item["url_hash"]
            adj = item.get("extra", {}).get("adjunct_supervisor", {})
            if adj and adj.get("status"):
                if not dry_run:
                    ann = annotations.setdefault(url_hash, {})
                    ann["adjunct_supervisor"] = adj
                    ann["relation_updated_at"] = now
                    ann["relation_updated_by"] = "excel_import"

    # Save annotation store
    if not dry_run and annotations:
        _save_json(ANNOTATIONS_FILE, annotations)
        logger.info("annotation store 已更新，共 %d 条", len(annotations))

    # Remove adjunct_import directory
    if not dry_run:
        shutil.rmtree(IMPORT_DIR.parent)  # removes adjunct_import/
        logger.info("已删除 adjunct_import/ 目录")

    print("\n" + "=" * 55)
    print(f"  分发完成{'（dry-run）' if dry_run else ''}")
    print("=" * 55)
    print(f"  总条数:     {len(items)}")
    print(f"  目标目录数: {len(groups)}")
    print(f"  新写入:     {total_written}")
    print("=" * 55)


def main() -> None:
    parser = argparse.ArgumentParser(description="重新分发 adjunct_import 学者到各机构目录")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不写入")
    args = parser.parse_args()
    redistribute(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
