"""
示例：使用通用脚本框架进行数据处理

原脚本：scripts/data_processing/import_institution_incremental.py (80+ 行)
新脚本：使用框架后约 40 行（减少 50%）
"""
from scripts.core import DataProcessingScript, DataTransformer, FileUtils


class ImportInstitutionsScript(DataProcessingScript):
    """增量导入机构数据"""

    def __init__(self):
        super().__init__(
            name="import_institutions",
            description="从 JSON 文件增量导入机构数据",
        )

    def add_arguments(self, parser):
        """添加自定义参数"""
        parser.add_argument("--input-file", required=True, help="输入 JSON 文件")
        parser.add_argument("--table", default="institutions", help="目标表名")

    async def run_async(self):
        """执行导入"""
        await self.init_database()

        # 1. 加载数据
        data = FileUtils.load_json(self.args.input_file)
        self.logger.info(f"加载了 {len(data)} 条记录")

        # 2. 字段映射
        mapping = {
            "name": "name",
            "name_en": "name_en",
            "entity_type": "entity_type",
            "region": "region",
            "org_type": "org_type",
            "classification": "classification",
            "sub_classification": "sub_classification",
        }

        # 3. 转换数据
        records = []
        for item in data:
            try:
                record = DataTransformer.map_fields(item, mapping)

                # 验证必填字段
                is_valid, missing = DataTransformer.validate_required_fields(record, ["name", "entity_type"])

                if not is_valid:
                    self.logger.warning(f"记录缺少必填字段 {missing}: {item.get('name')}")
                    self.update_stats("skipped")
                    continue

                records.append(record)
                self.update_stats("success")

            except Exception as e:
                self.logger.error(f"转换失败: {e}")
                self.update_stats("errors")

        # 4. 批量插入
        if records:
            result = await self.db_client.table(self.args.table).upsert(records).execute()
            self.logger.info(f"已导入 {len(result.data)} 条记录")

        # 5. 打印统计
        self.print_stats()


if __name__ == "__main__":
    script = ImportInstitutionsScript()
    script.execute()
