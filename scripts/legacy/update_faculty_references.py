#!/usr/bin/env python3
"""批量更新文件内容中的 faculty → scholar 引用"""
import re
from pathlib import Path


def update_file_content(filepath: Path) -> bool:
    """更新单个文件内容"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        original = content

        # 替换规则（按优先级排序，避免误替换）
        replacements = [
            # 模块导入
            (r"from app\.services\.faculty import", "from app.services.scholar import"),
            (r"from app\.services import scholar_service", "from app.services import scholar_service"),
            (r"from app\.services import faculty_annotation_store", "from app.services import scholar_annotation_store"),
            (r"from app\.schemas\.faculty import", "from app.schemas.scholar import"),
            (r"from app\.api\.v1 import faculty", "from app.api.v1 import scholars"),
            (r"from app\.crawlers\.templates\.faculty_crawler import", "from app.crawlers.templates.scholar_crawler import"),
            (r"from app\.crawlers\.utils\.faculty_llm_extractor import", "from app.crawlers.utils.scholar_llm_extractor import"),
            (r"from app\.crawlers\.parsers\.([\w_]+)_faculty import", r"from app.crawlers.parsers.\1_scholar import"),

            # 类名和函数名
            (r"\bFacultyListItem\b", "ScholarListItem"),
            (r"\bFacultyListResponse\b", "ScholarListResponse"),
            (r"\bFacultyDetailResponse\b", "ScholarDetailResponse"),
            (r"\bFacultySourceItem\b", "ScholarSourceItem"),
            (r"\bFacultySourcesResponse\b", "ScholarSourcesResponse"),
            (r"\bFacultyStatsResponse\b", "ScholarStatsResponse"),
            (r"\bFacultyBasicUpdate\b", "ScholarBasicUpdate"),
            (r"\bFacultyCrawler\b", "ScholarCrawler"),

            # 函数名
            (r"\bget_faculty_list\b", "get_scholar_list"),
            (r"\bget_faculty_detail\b", "get_scholar_detail"),
            (r"\bget_faculty_stats\b", "get_scholar_stats"),
            (r"\bget_faculty_sources\b", "get_scholar_sources"),
            (r"\bupdate_faculty_basic\b", "update_scholar_basic"),
            (r"\bupdate_faculty_relation\b", "update_scholar_relation"),
            (r"\bupdate_faculty_achievements\b", "update_scholar_achievements"),
            (r"\badd_faculty_update\b", "add_scholar_update"),
            (r"\bdelete_faculty_update\b", "delete_scholar_update"),
            (r"\bdelete_faculty\b", "delete_scholar"),
            (r"\blist_faculty\b", "list_scholars"),

            # 变量名和参数名（保守替换）
            (r"\bfaculty_service\b", "scholar_service"),
            (r"\bfaculty\.router\b", "scholars.router"),
            (r'prefix="/scholars"', 'prefix="/scholars"'),
            (r'tags=\["faculty"\]', 'tags=["scholars"]'),

            # 路径和维度名
            (r'"scholars"', '"scholars"'),
            (r"'scholars'", "'scholars'"),
            (r"/scholars/", "/scholars/"),
            (r"data/scholars", "data/scholars"),
            (r"faculty_annotations\.json", "scholar_annotations.json"),

            # 注释和文档字符串中的描述（保留中文"师资"不变）
            (r"Scholar API", "Scholar API"),
            (r"/api/v1/scholars/", "/api/v1/scholars/"),
            (r"GET  /scholars/", "GET  /scholars/"),
            (r"POST /scholars/", "POST /scholars/"),
            (r"PATCH /scholars/", "PATCH /scholars/"),
            (r"DELETE /scholars/", "DELETE /scholars/"),
        ]

        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content)

        if content != original:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        return False

    except Exception as e:
        print(f"  ✗ Error processing {filepath}: {e}")
        return False


def main():
    base_dir = Path(__file__).parent.parent

    # 需要更新的文件模式
    patterns = [
        "app/**/*.py",
        "sources/**/*.yaml",
        "scripts/**/*.py",
    ]

    updated_files = []

    for pattern in patterns:
        for filepath in base_dir.glob(pattern):
            if filepath.is_file() and "__pycache__" not in str(filepath):
                if update_file_content(filepath):
                    updated_files.append(filepath.relative_to(base_dir))
                    print(f"  ✓ Updated: {filepath.relative_to(base_dir)}")

    print(f"\n{'='*60}")
    print(f"Total files updated: {len(updated_files)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
