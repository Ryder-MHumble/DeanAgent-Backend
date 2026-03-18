"""
FileUtils - 统一的文件操作工具

消除重复：
- JSON/CSV 读写
- YAML 配置加载
- 文件路径处理
"""
import csv
import json
from pathlib import Path
from typing import Any

import yaml


class FileUtils:
    """文件操作工具集"""

    @staticmethod
    def load_json(file_path: Path | str) -> dict | list:
        """加载 JSON 文件"""
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def save_json(file_path: Path | str, data: dict | list, indent: int = 2):
        """保存 JSON 文件"""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)

    @staticmethod
    def load_yaml(file_path: Path | str) -> dict | list:
        """加载 YAML 文件"""
        with open(file_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    @staticmethod
    def save_yaml(file_path: Path | str, data: dict | list):
        """保存 YAML 文件"""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    @staticmethod
    def load_csv(file_path: Path | str, encoding: str = "utf-8") -> list[dict]:
        """加载 CSV 文件（返回字典列表）"""
        with open(file_path, encoding=encoding) as f:
            reader = csv.DictReader(f)
            return list(reader)

    @staticmethod
    def save_csv(
        file_path: Path | str, data: list[dict], fieldnames: list[str] | None = None, encoding: str = "utf-8"
    ):
        """保存 CSV 文件"""
        if not data:
            return

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if not fieldnames:
            fieldnames = list(data[0].keys())

        with open(path, "w", encoding=encoding, newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

    @staticmethod
    def ensure_dir(dir_path: Path | str):
        """确保目录存在"""
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def list_files(dir_path: Path | str, pattern: str = "*") -> list[Path]:
        """列出目录下的文件"""
        return list(Path(dir_path).glob(pattern))
