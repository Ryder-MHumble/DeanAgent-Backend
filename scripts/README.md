# Scripts 目录说明

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
- `init_event_taxonomy.py`
- `migrate_event_categories.py`
- `rename_cas_to_ucas.py`

## core/ — 脚本公共模块

- `base_script.py`: 脚本基类
- `api_client.py`: HTTP 客户端
- `file_utils.py`: 文件工具
- `data_transformer.py`: 数据转换工具
- `progress_tracker.py`: 进度追踪

## examples/ — 示例脚本

- `data_import_example.py`
- `database_cleanup_example.py`
- `aminer_enrichment_example.py`

## 推荐迁移流程

```bash
# 1) 从 Supabase 拉取最新导出
python scripts/migration/export_supabase_to_sql.py --output-dir exports/sql

# 2) 导入本地 PostgreSQL（需 .env 中 POSTGRES_*）
bash scripts/migration/refresh_and_load_local.sh

# 3) 校验行数
python scripts/migration/verify_local_pg_counts.py
```
