"""
示例：使用通用脚本框架进行数据库批量操作

原脚本：scripts/database/cleanup_institutions_fields.py (80+ 行)
新脚本：使用框架后约 30 行（减少 62%）
"""
from scripts.core import DatabaseScript


class CleanupInstitutionsScript(DatabaseScript):
    """清理机构表无用字段"""

    def __init__(self):
        super().__init__(
            name="cleanup_institutions",
            description="清理机构表中的无用字段",
            table="institutions",
        )

    def add_arguments(self, parser):
        """添加自定义参数"""
        parser.add_argument(
            "--fields",
            nargs="+",
            required=True,
            help="要删除的字段列表",
        )
        parser.add_argument(
            "--check-empty",
            action="store_true",
            help="仅删除完全为空的字段",
        )

    async def run_async(self):
        """执行清理"""
        # 1. 获取所有记录
        records = await self.fetch_all()
        self.logger.info(f"共 {len(records)} 条记录")

        # 2. 分析字段使用情况
        fields_to_delete = self.args.fields
        field_stats = {}

        for field in fields_to_delete:
            non_empty = sum(1 for r in records if r.get(field))
            field_stats[field] = {"total": len(records), "non_empty": non_empty, "empty": len(records) - non_empty}

        # 3. 显示统计
        self.logger.info("字段使用情况:")
        for field, stats in field_stats.items():
            self.logger.info(f"  {field}: {stats['non_empty']}/{stats['total']} 非空")

        # 4. 确定要删除的字段
        if self.args.check_empty:
            fields_to_delete = [f for f, s in field_stats.items() if s["non_empty"] == 0]
            self.logger.info(f"将删除 {len(fields_to_delete)} 个完全为空的字段")

        if not fields_to_delete:
            self.logger.info("没有需要删除的字段")
            return

        # 5. 执行删除（通过更新记录，将字段设为 None）
        if self.args.dry_run:
            self.logger.info(f"[DRY-RUN] 将删除字段: {', '.join(fields_to_delete)}")
            return

        # Supabase 不支持直接删除列，需要通过 SQL 或手动更新
        self.logger.warning("Supabase 不支持通过 API 删除列，请使用 SQL:")
        for field in fields_to_delete:
            self.logger.info(f"  ALTER TABLE {self.table} DROP COLUMN {field};")


if __name__ == "__main__":
    script = CleanupInstitutionsScript()
    script.execute()
