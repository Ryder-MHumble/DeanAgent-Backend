# Scripts 目录说明

## 设计原则

- `scripts/` 只放“可直接复用的能力脚本”，不放 `test_*.py` 风格文件。
- 命名以用途为中心，优先使用动词或能力名（如 `verify_*` / `process_*` / `run_*`）。
- 每个脚本都应可独立运行，并给出明确输出（通过/失败/摘要）。
- 示例脚本放 `examples/`，通用校验与工具放 `core/`，迁移放 `migration/`。

## crawl/ — 爬取脚本

- `run_single.py`: 单源爬取测试
- `run_all.py`: 批量爬取（支持并发策略）

## intel/ — 智能处理脚本

- `process_policy.py`
- `process_personnel.py`
- `process_tech_frontier.py`
- `process_university_eco.py`

## migration/ — 数据迁移与结构维护

- `export_supabase_to_sql.py`: 从 Supabase 导出 schema/data 到 `exports/sql`
- `refresh_and_load_local.sh`: 一键执行导出 -> 导入本地 PostgreSQL -> 校验
- `verify_local_pg_counts.py`: 校验本地 PostgreSQL 行数是否与导出摘要一致
- `optimize_pg_performance.sql`: PostgreSQL 读写性能索引（可重复执行）
- `apply_pg_optimizations.sh`: 执行性能索引脚本（非 owner 时自动尝试 `sudo -u postgres`）
- `init_event_taxonomy.py`
- `migrate_event_categories.py`
- `rename_cas_to_ucas.py`

## core/ — 脚本公共模块

- `base_script.py`: 脚本基类
- `api_client.py`: HTTP 客户端
- `file_utils.py`: 文件工具
- `data_transformer.py`: 数据转换工具
- `progress_tracker.py`: 进度追踪
- `verify_event_tag_mapping.py`: 校验活动标签模型字段映射（cover_image_url/event_time 等）
- `verify_project_tag_mapping.py`: 校验项目标签模型兼容映射（subcategory/scholar_ids）
- `inspect_project_taxonomy.py`: 检查项目分类树加载结果

## examples/ — 示例脚本

- `data_import_example.py`
- `database_cleanup_example.py`
- `aminer_enrichment_example.py`
- `aminer_detail_api_diagnostic.py`: AMiner 学者详情 API 诊断示例

## 推荐迁移流程

```bash
# 1) 从 Supabase 拉取最新导出
python scripts/migration/export_supabase_to_sql.py --output-dir exports/sql

# 2) 导入本地 PostgreSQL（需 .env 中 POSTGRES_*）
bash scripts/migration/refresh_and_load_local.sh

# 3) 校验行数
python scripts/migration/verify_local_pg_counts.py

# 4) （可选）执行性能优化索引
# 若当前 DB 用户不是表 owner，脚本会自动尝试 sudo 切换到 postgres
bash scripts/migration/apply_pg_optimizations.sh
```
