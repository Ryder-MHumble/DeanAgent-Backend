# Scripts 目录说明

## 常用脚本（根目录）

| 脚本 | 说明 |
|------|------|
| `run_single_crawl.py` | ⭐ 单源爬虫测试：`python scripts/run_single_crawl.py --source <id>` |
| `run_all_crawl.py` | ⭐ 批量爬虫：`python scripts/run_all_crawl.py` |
| `rebuild_institutions.py` | ⭐ 重建 institutions.json：`python scripts/rebuild_institutions.py [--dry-run]` |
| `process_policy_intel.py` | ⭐ 政策智能处理：`python scripts/process_policy_intel.py [--dry-run]` |
| `process_personnel_intel.py` | ⭐ 人事情报处理：`python scripts/process_personnel_intel.py [--dry-run] [--enrich]` |
| `process_tech_frontier.py` | ⭐ 科技前沿处理：`python scripts/process_tech_frontier.py [--dry-run]` |
| `process_university_eco.py` | ⭐ 高校生态处理：`python scripts/process_university_eco.py` |

## data_import/ — 数据导入

从 Excel 或外部数据源导入数据到 JSON 存储。

| 脚本 | 说明 |
|------|------|
| `import_institutions_from_excel.py` | 从 Excel 导入高校合作信息 |
| `import_all_universities_from_excel.py` | 从 Excel 批量导入所有高校 |
| `import_events_from_excel.py` | 从 Excel 导入事件数据 |
| `import_supervised_students.py` | 导入在读/毕业生信息 |
| `rebuild_institutions_from_excel.py` | 从 Excel 重建 institutions.json |
| `read_excel_headers.py` | 查看 Excel 文件的列头信息 |

## data_enrich/ — 数据富化

通过外部 API 或 LLM 补全/增强现有数据。

| 脚本 | 说明 |
|------|------|
| `enrich_institutions_from_aminer.py` | 从 AMiner API 补全机构信息 |
| `enrich_institutions_from_excel.py` | 从 Excel 补全机构信息 |
| `enrich_aminer_org_name.py` | 补全机构的 AMiner org_name |
| `enrich_institutions_org_name.py` | 补全机构的英文 org_name |
| `enrich_faculty_data.py` | LLM 富化学者数据字段 |

## data_build/ — 数据构建

生成或合并处理后的数据文件。

| 脚本 | 说明 |
|------|------|
| `build_complete_institutions.py` | 构建完整的 institutions.json（多源合并） |
| `merge_institution_data.py` | 合并多个机构数据文件 |
| `normalize_institutions_schema.py` | 规范化 institutions.json 字段结构 |
| `generate_index.py` | 生成 data/index.json（前端索引） |

## legacy/ — 历史脚本

一次性迁移脚本或已完成使命的工具，**通常不需要执行**。

| 脚本 | 说明 |
|------|------|
| `migrate_faculty_to_scholars.py` | faculty → scholar 数据迁移（已完成） |
| `migrate_data_structure.py` | 数据目录结构迁移（已完成） |
| `migrate_json_to_latest.py` | 日期文件 → latest.json 格式迁移（已完成） |
| `update_faculty_references.py` | 批量更新代码中的 faculty 引用（已完成） |
| `validate_scholar_data.py` | 验证学者数据质量 |
| `test_all_faculty_sources.py` | 测试所有学者信源 |
| `test_institution_api.py` | 本地测试机构 API 逻辑 |
| `test_institutions_persistence.py` | 测试 institutions.json 持久化 |
| `query_llm_tracking.py` | 查询 LLM 调用追踪数据 |
| `aminer_examples.py` | AMiner API 调用示例 |
| `update_scholar_dimension.py` | 更新学者维度字段（已完成） |
