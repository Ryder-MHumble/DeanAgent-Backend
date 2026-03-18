"""
DataTransformer - 统一的数据转换工具

消除重复：
- 字段解析
- 数据验证
- Schema 映射
- 缺失值处理
"""
import json
import re
from typing import Any


class DataTransformer:
    """数据转换工具集"""

    @staticmethod
    def parse_json_field(value: Any) -> Any:
        """解析 JSON 字段（支持字符串/列表/字典）"""
        if value is None or value == "":
            return None

        if isinstance(value, (list, dict)):
            return value

        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value

        return value

    @staticmethod
    def parse_institution_name(name: str) -> dict[str, str]:
        """解析机构名称（提取中英文）

        示例:
            "清华大学 Tsinghua University" -> {"zh": "清华大学", "en": "Tsinghua University"}
            "清华大学" -> {"zh": "清华大学", "en": None}
        """
        if not name:
            return {"zh": None, "en": None}

        # 尝试分割中英文
        parts = name.split()
        zh_part = None
        en_part = None

        for part in parts:
            if re.search(r"[\u4e00-\u9fff]", part):  # 包含中文
                zh_part = part
            elif re.search(r"[a-zA-Z]", part):  # 包含英文
                en_part = part if not en_part else f"{en_part} {part}"

        return {"zh": zh_part or name, "en": en_part}

    @staticmethod
    def parse_education(education_data: Any) -> list[dict]:
        """解析教育经历

        支持格式:
        - 字符串: "清华大学 博士 2010-2015"
        - 列表: [{"school": "清华大学", "degree": "博士", "year": "2010-2015"}]
        - JSON 字符串
        """
        if not education_data:
            return []

        # 已经是列表
        if isinstance(education_data, list):
            return education_data

        # JSON 字符串
        if isinstance(education_data, str):
            try:
                parsed = json.loads(education_data)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass

            # 简单文本解析
            return [{"raw": education_data}]

        return []

    @staticmethod
    def parse_honors(honors_data: Any) -> list[dict]:
        """解析荣誉奖项

        支持格式:
        - 字符串: "国家杰青 2020"
        - 列表: [{"title": "国家杰青", "year": 2020}]
        - JSON 字符串
        """
        if not honors_data:
            return []

        if isinstance(honors_data, list):
            return honors_data

        if isinstance(honors_data, str):
            try:
                parsed = json.loads(honors_data)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass

            return [{"raw": honors_data}]

        return []

    @staticmethod
    def normalize_field(value: Any, field_type: str = "str") -> Any:
        """标准化字段值"""
        if value is None or value == "":
            return None

        if field_type == "str":
            return str(value).strip()
        elif field_type == "int":
            try:
                return int(value)
            except (ValueError, TypeError):
                return None
        elif field_type == "float":
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        elif field_type == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "yes", "1", "是")
            return bool(value)
        elif field_type == "list":
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return [value]
            return [value]

        return value

    @staticmethod
    def map_fields(
        source: dict, mapping: dict[str, str | tuple[str, str]], defaults: dict | None = None
    ) -> dict:
        """字段映射

        Args:
            source: 源数据
            mapping: 映射规则 {"target_field": "source_field"} 或 {"target_field": ("source_field", "type")}
            defaults: 默认值

        示例:
            mapping = {
                "name": "姓名",
                "age": ("年龄", "int"),
                "tags": ("标签", "list")
            }
        """
        result = {}

        for target_field, source_config in mapping.items():
            # 解析配置
            if isinstance(source_config, tuple):
                source_field, field_type = source_config
            else:
                source_field = source_config
                field_type = "str"

            # 获取值
            value = source.get(source_field)

            # 标准化
            value = DataTransformer.normalize_field(value, field_type)

            # 应用默认值
            if value is None and defaults and target_field in defaults:
                value = defaults[target_field]

            result[target_field] = value

        return result

    @staticmethod
    def validate_required_fields(record: dict, required_fields: list[str]) -> tuple[bool, list[str]]:
        """验证必填字段"""
        missing = []
        for field in required_fields:
            if field not in record or record[field] is None or record[field] == "":
                missing.append(field)

        return len(missing) == 0, missing

    @staticmethod
    def clean_text(text: str | None) -> str | None:
        """清理文本（去除多余空格、换行等）"""
        if not text:
            return None

        # 去除多余空格
        text = re.sub(r"\s+", " ", text)
        # 去除首尾空格
        text = text.strip()

        return text if text else None
