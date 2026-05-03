# 全局论文仓

## 目标

`papers` 是平台级论文主数据仓，用于统一沉淀来自多个论文爬虫任务的论文客体数据，便于后续检索、复用和与学生/学者 owner 关系做桥接。

本轮边界：

- 不替换现有 `student_publications` / `publications` / `publication_candidates`
- 不把 owner/compliance 字段写回论文客体表
- 不把结构化论文主数据压扁写入 `articles`

## 数据模型

对外核心字段：

- `doi`
- `title`
- `abstract`
- `publication_date`
- `authors`
- `affiliations`
- `source`

其中：

- `authors`: `string[]`
- `affiliations`: `[{author_order, author_name, affiliation}]`
- `source`: `{type, name, source_id}`

内部支撑表：

- `papers`: 论文主表
- `paper_ingest_runs`: 导入运行记录

数据库落表 SQL：

- [scripts/sql/20260429_create_paper_warehouse.sql](../scripts/sql/20260429_create_paper_warehouse.sql)

## 去重与合并

导入顺序：

1. 标准化 payload
2. 中文标题过滤
3. upsert `papers`
4. 记录 `paper_ingest_runs`

去重键优先级：

1. `doi`
2. `source_id + raw_id`
3. `normalized_title + publication_date`

合并规则：

- 只补空值
- `abstract` 取更长的非空值
- `authors` / `affiliations` 取信息更完整的一侧
- 主来源优先级：`raw_official > official_api > third_party_api`

过滤规则：

- 标题含中文字符的论文直接丢弃，不落库

## 信源配置

论文仓信源独立放在：

- [sources/paper/top_conference_papers.yaml](../sources/paper/top_conference_papers.yaml)

当前接入的顶会论文源已扩展到多年口径：

- source id：`acl_long`、`acl_short`、`iclr`、`neurips`、`cvpr`、`eccv`、`ijcai`、`aaai`

当前默认抓取窗口：

- ACL：2024-2025（Long / Short）
- ICLR：2024-2025（Main Conference）
- NeurIPS：2022-2024
- CVPR：2023-2025
- ECCV：2022、2024
- IJCAI：2023-2025（Main Track）
- AAAI：2024-2026

原始 parser 已验证的可扩展年份范围：

- ACL：2024-2025（Long / Short）
- ICLR：2023-2025
- NeurIPS：2021-2025
- CVPR：2022-2025
- ECCV：2022、2024
- IJCAI：2023-2025
- AAAI：2022-2026

这些 source 统一约定：

- `dimension: paper`
- `entity_family: paper_record`
- `persist_to_db: true`

限制说明：

- 没有 topic 关键词过滤
- 当前主要限制来自 venue 自身的 track 口径，而不是 topic：
  - ACL 当前只采 Long / Short
  - ICLR 当前只采 Main Conference
  - CVPR 当前只采 Main Conference，不含 Workshop
  - IJCAI 当前只采 Main Track
  - ICLR 官方 API 对 `ICLR.cc/2023/Conference` 当前返回 `0` 条，默认窗口因此使用 `2024-2025`
  - NeurIPS 官方 `papers.nips.cc/paper_files/paper/2025` 当前返回 `404`，默认窗口因此使用 `2022-2024`
  - AAAI 默认只抓 issue 页元数据，不在主回填里抓 detail 页机构补全，因此 `affiliations` 允许为空

## API

### `GET /api/papers`

支持参数：

- `q`
- `doi`
- `source_type`
- `source_name`
- `source_id`
- `venue`
- `venue_year`
- `date_from`
- `date_to`
- `has_abstract`
- `page`
- `page_size`
- `sort_by`
- `order`

示例：

```bash
curl "http://localhost:8000/api/papers?venue=ICLR&venue_year=2024&has_abstract=true"
```

### `GET /api/papers/{paper_id}`

返回单篇论文详情和当前主来源。

### `GET /api/papers/sources`

返回论文仓 source 列表、论文数量和最近一次导入状态。

### `POST /api/papers/sources/{source_id}/crawl`

触发单个论文仓 source 的抓取与入库。

示例：

```bash
curl -X POST "http://localhost:8000/api/papers/sources/cvpr/crawl"
```

### `GET /api/papers/import-runs`

按 `source_id`、`status` 查询导入运行记录。

## 回填脚本

支持按 source 过滤和 dry-run：

```bash
.venv/bin/python scripts/crawl/backfill_papers.py --dry-run
.venv/bin/python scripts/crawl/backfill_papers.py --source cvpr
.venv/bin/python scripts/crawl/backfill_papers.py --source iclr --source aaai
```

## 代码入口

- API: [app/api/papers.py](../app/api/papers.py)
- Schema: [app/schemas/paper.py](../app/schemas/paper.py)
- Service: [app/services/paper_service.py](../app/services/paper_service.py)
- Crawler 注册: [app/crawlers/registry.py](../app/crawlers/registry.py)
- 落库分流: [app/crawlers/utils/json_storage.py](../app/crawlers/utils/json_storage.py)
