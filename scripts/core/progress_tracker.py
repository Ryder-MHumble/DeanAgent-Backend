"""
ProgressTracker - 统一的进度追踪器

消除重复：
- JSON 进度文件管理
- 失败记录追踪
- 断点续传支持
"""
import json
from pathlib import Path
from typing import Any


class ProgressTracker:
    """进度追踪器（支持断点续传）"""

    def __init__(self, name: str, data_dir: Path | str = "data/progress"):
        self.name = name
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.progress_file = self.data_dir / f"{name}_progress.json"
        self.failed_file = self.data_dir / f"{name}_failed.json"

    def load_progress(self) -> dict[str, Any]:
        """加载进度"""
        if not self.progress_file.exists():
            return {"last_index": 0, "processed_ids": [], "metadata": {}}

        with open(self.progress_file, encoding="utf-8") as f:
            return json.load(f)

    def save_progress(
        self, last_index: int, processed_ids: list[str] | None = None, metadata: dict | None = None
    ):
        """保存进度"""
        data = {
            "last_index": last_index,
            "processed_ids": processed_ids or [],
            "metadata": metadata or {},
        }

        with open(self.progress_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_failed(self) -> list[dict]:
        """加载失败记录"""
        if not self.failed_file.exists():
            return []

        with open(self.failed_file, encoding="utf-8") as f:
            return json.load(f)

    def save_failed(self, failed_records: list[dict]):
        """保存失败记录"""
        with open(self.failed_file, "w", encoding="utf-8") as f:
            json.dump(failed_records, f, ensure_ascii=False, indent=2)

    def append_failed(self, record: dict):
        """追加失败记录"""
        failed = self.load_failed()
        failed.append(record)
        self.save_failed(failed)

    def clear(self):
        """清除所有进度"""
        if self.progress_file.exists():
            self.progress_file.unlink()
        if self.failed_file.exists():
            self.failed_file.unlink()

    def is_resumable(self) -> bool:
        """是否可以断点续传"""
        return self.progress_file.exists()

    def get_last_index(self) -> int:
        """获取上次处理到的索引"""
        progress = self.load_progress()
        return progress.get("last_index", 0)

    def is_processed(self, record_id: str) -> bool:
        """检查记录是否已处理"""
        progress = self.load_progress()
        return record_id in progress.get("processed_ids", [])
