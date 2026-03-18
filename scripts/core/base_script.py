"""
BaseScript - 统一的脚本基类，封装通用功能

消除重复：
- 数据库初始化
- 日志配置
- 参数解析
- 错误处理
- 进度追踪
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

from app.db.client import get_client, init_client


class BaseScript:
    """所有脚本的基类，提供通用功能"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.logger = self._setup_logging()
        self.args = None
        self.db_client = None

    def _setup_logging(self) -> logging.Logger:
        """配置日志（文件 + 控制台）"""
        log_dir = Path("logs/scripts")
        log_dir.mkdir(parents=True, exist_ok=True)

        logger = logging.getLogger(self.name)
        logger.setLevel(logging.INFO)

        # 文件处理器
        fh = logging.FileHandler(log_dir / f"{self.name}.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)

        # 控制台处理器
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # 格式化
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        logger.addHandler(fh)
        logger.addHandler(ch)

        return logger

    def add_arguments(self, parser: argparse.ArgumentParser):
        """子类重写此方法添加自定义参数"""
        pass

    def create_parser(self) -> argparse.ArgumentParser:
        """创建参数解析器（带通用参数）"""
        parser = argparse.ArgumentParser(description=self.description)

        # 通用参数
        parser.add_argument("--dry-run", action="store_true", help="预览模式，不执行实际操作")
        parser.add_argument("--limit", type=int, help="限制处理记录数")
        parser.add_argument("--resume", action="store_true", help="从上次中断处继续")
        parser.add_argument("--force", action="store_true", help="强制重新处理")
        parser.add_argument("--verbose", action="store_true", help="详细日志输出")
        parser.add_argument("--output", type=str, help="输出文件路径")
        parser.add_argument("--input", type=str, help="输入文件路径")

        # 让子类添加自定义参数
        self.add_arguments(parser)

        return parser

    async def init_database(self):
        """初始化数据库连接"""
        import os

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")

        if not url or not key:
            self.logger.error("缺少 SUPABASE_URL 或 SUPABASE_KEY 环境变量")
            sys.exit(1)

        await init_client(url, key)
        self.db_client = get_client()
        self.logger.info("数据库连接已初始化")

    async def run_async(self):
        """子类实现此方法（异步版本）"""
        raise NotImplementedError("子类必须实现 run_async() 方法")

    def run_sync(self):
        """子类实现此方法（同步版本）"""
        raise NotImplementedError("子类必须实现 run_sync() 方法")

    def execute(self):
        """执行脚本（自动处理同步/异步）"""
        parser = self.create_parser()
        self.args = parser.parse_args()

        if self.args.verbose:
            self.logger.setLevel(logging.DEBUG)

        self.logger.info(f"开始执行脚本: {self.name}")
        self.logger.info(f"参数: {vars(self.args)}")

        try:
            # 尝试异步执行
            if hasattr(self, "run_async") and callable(self.run_async):
                asyncio.run(self._async_wrapper())
            else:
                self.run_sync()

            self.logger.info(f"脚本执行完成: {self.name}")

        except KeyboardInterrupt:
            self.logger.warning("脚本被用户中断")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"脚本执行失败: {e}", exc_info=True)
            sys.exit(1)

    async def _async_wrapper(self):
        """异步执行包装器"""
        await self.init_database()
        await self.run_async()


class DatabaseScript(BaseScript):
    """数据库操作脚本基类"""

    def __init__(self, name: str, description: str, table: str):
        super().__init__(name, description)
        self.table = table

    async def fetch_all(self, select: str = "*", filters: dict[str, Any] | None = None):
        """获取所有记录"""
        query = self.db_client.table(self.table).select(select)

        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)

        response = await query.execute()
        return response.data

    async def insert_batch(self, records: list[dict], batch_size: int = 100):
        """批量插入"""
        total = len(records)
        success = 0
        errors = []

        for i in range(0, total, batch_size):
            batch = records[i : i + batch_size]

            if self.args.dry_run:
                self.logger.info(f"[DRY-RUN] 将插入 {len(batch)} 条记录")
                success += len(batch)
                continue

            try:
                await self.db_client.table(self.table).insert(batch).execute()
                success += len(batch)
                self.logger.info(f"已插入 {success}/{total} 条记录")
            except Exception as e:
                self.logger.error(f"批次插入失败: {e}")
                errors.extend(batch)

        return {"success": success, "errors": errors}

    async def update_batch(self, records: list[dict], id_field: str = "id", batch_size: int = 100):
        """批量更新"""
        total = len(records)
        success = 0
        errors = []

        for i in range(0, total, batch_size):
            batch = records[i : i + batch_size]

            if self.args.dry_run:
                self.logger.info(f"[DRY-RUN] 将更新 {len(batch)} 条记录")
                success += len(batch)
                continue

            for record in batch:
                try:
                    record_id = record.pop(id_field)
                    await (
                        self.db_client.table(self.table)
                        .update(record)
                        .eq(id_field, record_id)
                        .execute()
                    )
                    success += 1
                except Exception as e:
                    self.logger.error(f"更新记录失败 ({record_id}): {e}")
                    errors.append(record)

            self.logger.info(f"已更新 {success}/{total} 条记录")

        return {"success": success, "errors": errors}

    async def delete_batch(self, ids: list[Any], id_field: str = "id"):
        """批量删除"""
        if self.args.dry_run:
            self.logger.info(f"[DRY-RUN] 将删除 {len(ids)} 条记录")
            return {"success": len(ids), "errors": []}

        success = 0
        errors = []

        for record_id in ids:
            try:
                await self.db_client.table(self.table).delete().eq(id_field, record_id).execute()
                success += 1
            except Exception as e:
                self.logger.error(f"删除记录失败 ({record_id}): {e}")
                errors.append(record_id)

        self.logger.info(f"已删除 {success}/{len(ids)} 条记录")
        return {"success": success, "errors": errors}


class DataProcessingScript(BaseScript):
    """数据处理脚本基类"""

    def __init__(self, name: str, description: str):
        super().__init__(name, description)
        self.stats = {"processed": 0, "success": 0, "errors": 0, "skipped": 0}

    def update_stats(self, status: str):
        """更新统计信息"""
        self.stats["processed"] += 1
        if status in self.stats:
            self.stats[status] += 1

    def print_stats(self):
        """打印统计信息"""
        self.logger.info("=" * 50)
        self.logger.info("执行统计:")
        for key, value in self.stats.items():
            self.logger.info(f"  {key}: {value}")
        self.logger.info("=" * 50)
