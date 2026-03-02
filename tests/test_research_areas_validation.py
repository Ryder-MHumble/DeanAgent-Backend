import pytest
from app.schemas.scholar import validate_research_areas


def test_nav_menu_pollution_detected():
    """导航菜单条目应被整体清空"""
    nav_items = [
        "首页", "关于我们", "中心简介", "行政团队", "中心动态",
        "访问指南", "数学学人", "领军学者", "专业委员会", "中心教师",
        "博士后", "来访学者", "清华学者库", "人才培养", "国内博士招生",
        "海外博士招生", "暑期学校", "中学夏令营", "在读研究生", "学生动态",
    ]
    assert validate_research_areas(nav_items) == []


def test_too_many_items_detected():
    """超过 15 个条目视为污染"""
    many_items = [f"方向{i}" for i in range(16)]
    assert validate_research_areas(many_items) == []


def test_avg_length_too_short_detected():
    """平均字符数 < 3 视为污染"""
    short_items = ["A", "B", "C", "D"]
    assert validate_research_areas(short_items) == []


def test_valid_research_areas_pass():
    """正常研究方向不受影响"""
    valid = ["机器学习", "计算机视觉", "自然语言处理"]
    assert validate_research_areas(valid) == valid


def test_empty_list_passes():
    assert validate_research_areas([]) == []


def test_single_valid_item_passes():
    assert validate_research_areas(["深度学习"]) == ["深度学习"]


def test_exactly_15_items_passes():
    """恰好 15 个条目应通过"""
    items = [f"研究方向{i}" for i in range(15)]
    assert validate_research_areas(items) == items


def test_mixed_valid_with_one_nav_keyword():
    """只要有一个导航词就整体清空"""
    mixed = ["机器学习", "首页", "计算机视觉"]
    assert validate_research_areas(mixed) == []
