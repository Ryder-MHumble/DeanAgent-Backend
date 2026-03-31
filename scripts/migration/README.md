# Migration Scripts Guide

当前目录仅保留“本地库刷新 + 校验 + 性能优化”相关脚本。

## 保留脚本

- `export_supabase_to_sql.py`
  - 从 Supabase 导出 schema/data 到 `exports/sql`
- `refresh_and_load_local.sh`
  - 一键执行导出 -> 导入本地 PostgreSQL -> 校验
- `verify_local_pg_counts.py`
  - 校验本地 PostgreSQL 行数与导出摘要一致
- `create_university_leadership_tables.sql`
  - 在本地导入后补充高校领导力表结构
- `optimize_pg_performance.sql`
  - PostgreSQL 索引优化 SQL（可重复执行）
- `apply_pg_optimizations.sh`
  - 执行性能索引脚本（包含 owner/权限处理）

## 推荐流程

```bash
# 1) 导出远端 Supabase
python scripts/migration/export_supabase_to_sql.py --output-dir exports/sql

# 2) 刷新本地 PostgreSQL（含表结构补充）
bash scripts/migration/refresh_and_load_local.sh

# 3) 校验数据行数
python scripts/migration/verify_local_pg_counts.py

# 4) 可选：执行性能优化索引
bash scripts/migration/apply_pg_optimizations.sh
```
