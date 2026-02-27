# tests/test_source_filter.py
import pytest
from app.services.intel.shared import parse_source_filter


def test_parse_source_filter_returns_none_when_all_params_empty():
    """所有参数为空时返回 None（不筛选）"""
    result = parse_source_filter(None, None, None, None)
    assert result is None


def test_parse_source_filter_single_id():
    """单个 source_id"""
    result = parse_source_filter("gov_cn_zhengce", None, None, None)
    assert result == {"gov_cn_zhengce"}


def test_parse_source_filter_multiple_ids():
    """逗号分隔的多个 source_ids"""
    result = parse_source_filter(None, "id1,id2,id3", None, None)
    assert result == {"id1", "id2", "id3"}


def test_parse_source_filter_whitespace_handling():
    """处理空白字符和空项"""
    result = parse_source_filter(" id1 ", " id2 , , id3 ", None, None)
    assert result == {"id1", "id2", "id3"}


def test_parse_source_filter_deduplication():
    """去重：source_id 和 source_ids 中有重复"""
    result = parse_source_filter("id1", "id1,id2", None, None)
    assert result == {"id1", "id2"}


def test_parse_source_filter_all_empty_strings():
    """全是空字符串时返回空集合"""
    result = parse_source_filter("", " , , ", None, None)
    assert result == set()
