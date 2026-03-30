# Migration Scripts Guide

这个目录已按两个维度整理：
- 能力（Capability）：脚本解决哪一类问题
- 复用性（Reuse）：脚本是否适合长期复用

## 推荐入口

- 机构清洗统一入口：
  - `scripts/migration/fix_scholar_institutions.py`（默认 `--scope global`）
- 目录清单查看：
  - `scripts/migration/list_migrations.py --format table`
  - `scripts/migration/list_migrations.py --format json`
- 统一执行入口：
  - `scripts/migration/run_migration.py --list`
  - `scripts/migration/run_migration.py --run fix_scholar_institutions.py --dry-run -- --scope global`

## 能力分组（Capability）

- `Schema / DDL`
  - 表结构变更、字段补齐、一次性 schema 升级 SQL
- `Performance`
  - 索引与执行优化脚本
- `Export / Sync`
  - Supabase 导出、本地库刷新
- `Verification`
  - 数据量、行数一致性校验
- `Data Cleanup`
  - 学者机构字段归一、地域修正、L1/L2 聚合
- `Data Import`
  - CSV/XLSX 导入、历史字段迁移
- `Data Tagging`
  - 批量补标签（往往偏一次性）
- `Taxonomy`
  - 分类体系初始化与迁移

## 复用性规则（Reuse）

- `High`：幂等、参数清晰、可反复执行（推荐长期保留）
- `Medium`：可复用但依赖项目数据格式/文件路径
- `Low`：强项目特定、一次性补数/修复脚本

## 聚合策略（已执行）

1. 机构清洗类脚本统一到 `fix_scholar_institutions.py`
   - `global`：推荐，覆盖最完整
     - 默认包含：学者机构归一 + 海外机构纠偏 + 机构表 L1/L2 转换（一级机构转二级机构）
     - 如仅做学者与地域纠偏，可加：`--skip-org-row-conversion`
   - `domestic/full`：保留兼容，作为 legacy scope
2. 新增机器可读目录 `catalog.py`
   - 标注 `status`、`canonical`、`superseded_by`
3. 新增 `list_migrations.py`
   - 统一输出目录分组，方便筛选/治理
4. 物理归档完成
   - `scripts/migration/archive/legacy/`：兼容保留的旧脚本
   - `scripts/migration/archive/oneoff/`：一次性脚本（保留审计）
5. 新增可复用组件
   - `scripts/migration/components/runtime.py`：统一 Postgres 初始化/获取/关闭生命周期
6. 新增统一执行器
   - `scripts/migration/run_migration.py`：基于 `catalog.py` 按脚本名执行

## Legacy 说明

下列脚本建议不再直接作为首选入口：
- `archive/legacy/fix_scholar_institutions_domestic_cleanup.py`
- `archive/legacy/fix_scholar_institutions_full.py`

建议改用：
- `fix_scholar_institutions.py --scope global`
