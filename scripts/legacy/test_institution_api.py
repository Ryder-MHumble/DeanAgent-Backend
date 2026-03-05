#!/usr/bin/env python3
"""测试 Institution API 的核心逻辑（不启动服务器）"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.services import institution_service as svc


def test_list_institutions():
    """测试机构列表查询"""
    print("=" * 60)
    print("测试 1: 获取所有机构列表（前 5 条）")
    print("=" * 60)
    result = svc.get_institution_list(page=1, page_size=5)
    print(f"总数: {result.total}")
    print(f"总页数: {result.total_pages}")
    print(f"\n前 5 条机构:")
    for item in result.items:
        print(f"  - [{item.type}] {item.name} (ID: {item.id})")
        if item.type == "university":
            print(f"    分类: {item.category}, 优先级: {item.priority}, 学者数: {item.scholar_count}")
        else:
            print(f"    父机构: {item.parent_id}, 学者数: {item.scholar_count}")
    print()


def test_filter_universities():
    """测试筛选高校"""
    print("=" * 60)
    print("测试 2: 筛选高校（type=university）")
    print("=" * 60)
    result = svc.get_institution_list(type_filter="university", page=1, page_size=10)
    print(f"高校总数: {result.total}")
    print(f"\n高校列表:")
    for item in result.items:
        print(f"  - {item.name} (ID: {item.id})")
        print(f"    分类: {item.category}, 优先级: {item.priority}, 学者数: {item.scholar_count}")
    print()


def test_filter_departments():
    """测试筛选院系"""
    print("=" * 60)
    print("测试 3: 筛选院系（type=department, parent_id=tsinghua）")
    print("=" * 60)
    result = svc.get_institution_list(
        type_filter="department",
        parent_id="tsinghua",
        page=1,
        page_size=10
    )
    print(f"清华大学院系总数: {result.total}")
    print(f"\n院系列表:")
    for item in result.items:
        print(f"  - {item.name} (ID: {item.id})")
        print(f"    学者数: {item.scholar_count}")
    print()


def test_university_detail():
    """测试高校详情"""
    print("=" * 60)
    print("测试 4: 获取清华大学详情")
    print("=" * 60)
    result = svc.get_institution_detail("tsinghua")
    if result:
        print(f"ID: {result.id}")
        print(f"名称: {result.name}")
        print(f"类型: {result.type}")
        print(f"分类: {result.category}")
        print(f"优先级: {result.priority}")
        print(f"学者总数: {result.scholar_count}")
        print(f"学生总数: {result.student_count_total}")
        print(f"导师总数: {result.mentor_count}")
        print(f"\n院系数量: {len(result.departments)}")
        print(f"重要学者数量: {len(result.notable_scholars)}")
        print(f"校领导数量: {len(result.university_leaders)}")

        if result.notable_scholars:
            print(f"\n前 3 位重要学者:")
            for scholar in result.notable_scholars[:3]:
                print(f"  - {scholar.name} ({scholar.title})")
                print(f"    院系: {scholar.department}, 研究方向: {scholar.research_area}")
    else:
        print("未找到清华大学")
    print()


def test_department_detail():
    """测试院系详情"""
    print("=" * 60)
    print("测试 5: 获取清华大学计算机系详情")
    print("=" * 60)
    result = svc.get_institution_detail("tsinghua_计算机科学与技术系")
    if result:
        print(f"ID: {result.id}")
        print(f"名称: {result.name}")
        print(f"类型: {result.type}")
        print(f"父机构: {result.parent_id}")
        print(f"学者数: {result.scholar_count}")
        print(f"\n信源数量: {len(result.sources)}")
        for source in result.sources:
            print(f"  - {source.source_name}")
            print(f"    ID: {source.source_id}, 学者数: {source.scholar_count}, 启用: {source.is_enabled}")
    else:
        print("未找到计算机系")
    print()


def test_stats():
    """测试统计信息"""
    print("=" * 60)
    print("测试 6: 获取统计信息")
    print("=" * 60)
    result = svc.get_institution_stats()
    print(f"高校总数: {result.total_universities}")
    print(f"院系总数: {result.total_departments}")
    print(f"学者总数: {result.total_scholars}")
    print(f"学生总数: {result.total_students}")
    print(f"导师总数: {result.total_mentors}")

    print(f"\n按分类统计:")
    for item in result.by_category:
        print(f"  - {item['category']}: {item['count']}")

    print(f"\n按优先级统计:")
    for item in result.by_priority:
        print(f"  - {item['priority']}: {item['count']}")
    print()


def test_keyword_search():
    """测试关键词搜索"""
    print("=" * 60)
    print("测试 7: 关键词搜索（keyword=计算机）")
    print("=" * 60)
    result = svc.get_institution_list(keyword="计算机", page=1, page_size=10)
    print(f"匹配结果数: {result.total}")
    print(f"\n匹配的机构:")
    for item in result.items:
        print(f"  - [{item.type}] {item.name} (ID: {item.id})")
    print()


def main():
    try:
        test_list_institutions()
        test_filter_universities()
        test_filter_departments()
        test_university_detail()
        test_department_detail()
        test_stats()
        test_keyword_search()

        print("=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
