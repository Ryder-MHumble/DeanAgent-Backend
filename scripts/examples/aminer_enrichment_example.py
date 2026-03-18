"""
示例：使用通用脚本框架重写 AMiner 学者富化脚本

原脚本：scripts/aminer_enrichment/enrich_scholars_from_aminer_serial.py (572 行)
新脚本：使用框架后约 150 行（减少 73%）
"""
import asyncio
from pathlib import Path

from scripts.core import (
    AMinerClient,
    BaseScript,
    DataTransformer,
    FileUtils,
    ProgressTracker,
)


class AMinerEnrichmentScript(BaseScript):
    """AMiner 学者富化脚本"""

    def __init__(self):
        super().__init__(
            name="aminer_enrichment",
            description="从 AMiner API 富化学者数据",
        )
        self.tracker = ProgressTracker("aminer_enrichment")
        self.aminer_client = None

    def add_arguments(self, parser):
        """添加自定义参数"""
        parser.add_argument("--input-file", required=True, help="输入 Excel/CSV 文件")
        parser.add_argument("--output-file", help="输出 JSON 文件（默认：data/enriched_scholars.json）")
        parser.add_argument("--api-key", help="AMiner API Key（或使用环境变量 AMINER_API_KEY）")
        parser.add_argument("--rate-limit", type=float, default=0.5, help="API 请求间隔（秒）")

    async def run_async(self):
        """执行富化流程"""
        # 1. 初始化 AMiner 客户端
        import os

        api_key = self.args.api_key or os.getenv("AMINER_API_KEY")
        if not api_key:
            self.logger.error("缺少 AMiner API Key")
            return

        self.aminer_client = AMinerClient(api_key)
        self.aminer_client.rate_limit = self.args.rate_limit

        # 2. 加载输入数据
        input_file = Path(self.args.input_file)
        if input_file.suffix == ".csv":
            scholars = FileUtils.load_csv(input_file)
        elif input_file.suffix in (".xlsx", ".xls"):
            import pandas as pd

            df = pd.read_excel(input_file)
            scholars = df.to_dict("records")
        else:
            self.logger.error(f"不支持的文件格式: {input_file.suffix}")
            return

        self.logger.info(f"加载了 {len(scholars)} 条学者记录")

        # 3. 断点续传
        start_index = 0
        if self.args.resume and self.tracker.is_resumable():
            start_index = self.tracker.get_last_index()
            self.logger.info(f"从第 {start_index} 条记录继续")

        # 4. 处理每条记录
        enriched = []
        failed = []

        for i, scholar in enumerate(scholars[start_index:], start=start_index):
            if self.args.limit and i >= self.args.limit:
                break

            try:
                enriched_scholar = await self._enrich_scholar(scholar)
                enriched.append(enriched_scholar)

                # 保存进度
                if i % 10 == 0:
                    self.tracker.save_progress(i, [s["id"] for s in enriched])

                self.logger.info(f"已处理 {i + 1}/{len(scholars)}: {scholar.get('name', 'Unknown')}")

            except Exception as e:
                self.logger.error(f"处理失败 ({scholar.get('name')}): {e}")
                failed.append({"scholar": scholar, "error": str(e)})

        # 5. 保存结果
        output_file = self.args.output or "data/enriched_scholars.json"
        FileUtils.save_json(output_file, enriched)
        self.logger.info(f"已保存 {len(enriched)} 条富化记录到 {output_file}")

        if failed:
            self.tracker.save_failed(failed)
            self.logger.warning(f"有 {len(failed)} 条记录失败，已保存到失败文件")

    async def _enrich_scholar(self, scholar: dict) -> dict:
        """富化单个学者"""
        # 1. 解析机构名称
        institution = scholar.get("institution", "")
        inst_info = DataTransformer.parse_institution_name(institution)

        # 2. 搜索机构
        org_results = await self.aminer_client.search_organizations(inst_info["zh"] or inst_info["en"])
        org_id = org_results[0]["id"] if org_results else None

        # 3. 搜索学者
        name = scholar.get("name", "")
        scholar_results = await self.aminer_client.search_scholars(name, org_id)

        if not scholar_results:
            return self._create_base_record(scholar)

        # 4. 获取详情
        aminer_id = scholar_results[0]["id"]
        detail = await self.aminer_client.get_scholar_detail(aminer_id)

        if not detail:
            return self._create_base_record(scholar)

        # 5. 映射字段
        mapping = {
            "name": "name",
            "name_zh": "name_zh",
            "email": "email",
            "homepage": "homepage",
            "h_index": ("h_index", "int"),
            "n_citation": ("n_citation", "int"),
            "n_pubs": ("n_pubs", "int"),
            "tags": ("tags", "list"),
        }

        enriched = DataTransformer.map_fields(detail, mapping)

        # 6. 解析复杂字段
        enriched["education"] = DataTransformer.parse_education(detail.get("education"))
        enriched["honors"] = DataTransformer.parse_honors(detail.get("awards"))

        # 7. 保留原始字段
        enriched["original_data"] = scholar
        enriched["aminer_id"] = aminer_id

        return enriched

    def _create_base_record(self, scholar: dict) -> dict:
        """创建基础记录（未找到 AMiner 数据）"""
        return {
            "name": scholar.get("name"),
            "institution": scholar.get("institution"),
            "original_data": scholar,
            "aminer_id": None,
            "enriched": False,
        }


if __name__ == "__main__":
    script = AMinerEnrichmentScript()
    script.execute()
