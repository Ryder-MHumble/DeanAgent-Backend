# AI 顶刊顶会论文仓信源爬虫说明

> 最后更新: 2026-05-07

本文专门记录 `papers` 全局论文仓的 AI 顶刊顶会信源、爬虫方式、年份口径、字段覆盖和当前写库状态。README 只保留索引，论文仓数据模型与 API 见 [paper_warehouse.md](paper_warehouse.md)。

## 总览

配置文件：

- [sources/paper/top_conference_papers.yaml](../sources/paper/top_conference_papers.yaml)

统一约定：

- `dimension: paper`
- `entity_family: paper_record`
- `persist_to_db: true`
- `is_enabled: false`，通过回填脚本或 API 手动触发

回填入口：

```bash
.venv/bin/python scripts/crawl/backfill_papers.py --dry-run
.venv/bin/python scripts/crawl/backfill_papers.py --source jmlr --source jair --source tmlr
.venv/bin/python scripts/crawl/backfill_papers.py --source icml --source iccv --source emnlp_main
```

API 触发入口：

```bash
curl -X POST "http://localhost:8000/api/papers/sources/{source_id}/crawl"
```

## 当前论文仓信源

| source_id | Venue | 类型 | 年份口径 | crawler_class | 数据来源 |
|---|---|---|---|---|---|
| `jmlr` | JMLR | 顶刊 | 2023-2026 | `jmlr_papers` | JMLR volume index + abs 页 |
| `jair` | JAIR | 顶刊 | 2023-2026 | `jair_oai` | JAIR OAI-PMH `oai_dc` |
| `tmlr` | TMLR | 顶刊 | 2023-2026 | `openreview_journal` | OpenReview API |
| `acl_long` | ACL | 顶会 | 2024-2025 | `aclanthology` | ACL Anthology BibTeX |
| `acl_short` | ACL | 顶会 | 2024-2025 | `aclanthology` | ACL Anthology BibTeX |
| `iclr` | ICLR | 顶会 | 2024-2026 | `openreview` | OpenReview API |
| `icml` | ICML | 顶会 | 2023-2026 | `openreview` | OpenReview API / ICML virtual JSON |
| `neurips` | NeurIPS | 顶会 | 2022-2026（2026 proceedings 未发布前自动跳过） | `nips_papers_cc` | NeurIPS official proceedings |
| `cvpr` | CVPR | 顶会 | 2023-2026 | `cvf_openaccess` | CVF OpenAccess；2026 暂走 CVPR virtual |
| `iccv` | ICCV | 顶会 | 2023、2025 | `cvf_openaccess` | CVF OpenAccess |
| `emnlp_main` | EMNLP | 顶会 | 2023-2025 | `aclanthology` | ACL Anthology BibTeX |
| `eccv` | ECCV | 顶会 | 2022、2024 | `ecva_papers` | ECVA proceedings |
| `ijcai` | IJCAI | 顶会 | 2023-2025 | `ijcai_proceedings` | IJCAI proceedings |
| `aaai` | AAAI | 顶会 | 2024-2026 | `ojs_aaai` | AAAI OJS issues |

## 新增 2023-2025 信源写库结果

以下统计来自 `papers` 表，查询时间为 2026-05-03。

| source_id | 年份分布 | 当前总量 | 标题 | 作者 | 摘要 | PDF | DOI | 机构 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `jmlr` | 2023: 401；2024: 421；2025: 308 | 1,130 | 1,130 | 1,130 | 1,130 | 1,130 | 0 | 0 |
| `jair` | 2023: 100；2024: 105；2025: 132 | 337 | 337 | 337 | 337 | 337 | 337 | 0 |
| `tmlr` | 2023: 611；2024: 955；2025: 1,432 | 2,998 | 2,998 | 2,998 | 2,998 | 2,998 | 0 | 0 |
| `icml` | 2023: 1,828；2024: 2,610；2025: 3,257 | 7,695 | 7,695 | 7,695 | 7,695 | 7,695 | 0 | 0 |
| `iccv` | 2023: 2,156；2025: 2,701 | 4,857 | 4,857 | 4,857 | 0 | 4,857 | 0 | 0 |
| `emnlp_main` | 2023: 1,047；2024: 1,268；2025: 1,809 | 4,124 | 4,124 | 4,049 | 1 | 4,124 | 4,118 | 0 |

结论：

- 条目级基础数据已入库：标题、年份、详情页、PDF 链接覆盖较完整。
- 作者字段：除 `emnlp_main` 少量缺失外，其余新增源全量覆盖。
- 摘要字段：`jmlr`、`jair`、`tmlr`、`icml` 已全量覆盖；`iccv` 和 `emnlp_main` 需要后续补 detail 页摘要。
- DOI 字段：`jair` 全量覆盖，`emnlp_main` 基本覆盖；`jmlr`、`tmlr`、`icml`、`iccv` 当前源侧 DOI 不稳定或缺失。
- 机构字段：新增 6 源当前均未覆盖，需要后续通过 OpenAlex、OpenReview profile 或 PDF 首页补全。

## 单源说明

### JMLR

- source_id: `jmlr`
- crawler: [jmlr_papers.py](../app/crawlers/parsers/jmlr_papers.py)
- 方式：抓取 JMLR volume index，再进入 abs 页获取摘要和 citation meta。
- 年份：2023-2026，对应 volume 24、25、26、27。
- 已验证字段：`title`、`authors`、`abstract`、`publication_date`、`detail_url`、`pdf_url`。
- 当前缺口：DOI、机构。

### JAIR

- source_id: `jair`
- crawler: [jair_oai.py](../app/crawlers/parsers/jair_oai.py)
- 方式：抓取 OAI-PMH `ListRecords&metadataPrefix=oai_dc`，按 `dc:date` 过滤出版年份。
- 年份：2023-2026。
- 已验证字段：`title`、`authors`、`abstract`、`publication_date`、`detail_url`、`pdf_url`、`doi`。
- 处理细节：JAIR OAI XML 存在少量 XML 1.0 非法控制字符，parser 入库前会清洗。
- 当前缺口：机构。

### TMLR

- source_id: `tmlr`
- crawler: [openreview_journal.py](../app/crawlers/parsers/openreview_journal.py)
- 方式：抓取 OpenReview `content.venueid=TMLR`，按 note 的 `pdate/odate/cdate` 切入年份。
- 年份：2023-2026。
- 已验证字段：`title`、`authors`、`abstract`、`publication_date`、`detail_url`、`pdf_url`。
- 处理细节：OpenReview note 中可能出现 PostgreSQL 不接受的 `\x00`，`paper_service.normalize_payload()` 会清洗。
- 当前缺口：DOI、机构。

### ICML

- source_id: `icml`
- crawler: [openreview_api.py](../app/crawlers/parsers/openreview_api.py)
- 方式：抓取 OpenReview `ICML.cc/{year}/Conference`。
- 年份：2023-2026。2026 当前走 ICML virtual JSON，包含作者机构字段。
- 已验证字段：`title`、`authors`、`abstract`、`publication_date`、`detail_url`、`pdf_url`。
- 当前缺口：DOI、机构。

### ICCV

- source_id: `iccv`
- crawler: [cvf_openaccess.py](../app/crawlers/parsers/cvf_openaccess.py)
- 方式：抓取 CVF OpenAccess 列表页。
- 年份：2023、2025。ICCV 是双年会，当前不配置 2024。
- 已验证字段：`title`、`authors`、`publication_date`、`detail_url`、`pdf_url`。
- 当前缺口：摘要、DOI、机构。

### CVPR

- source_id: `cvpr`
- crawler: [cvf_openaccess.py](../app/crawlers/parsers/cvf_openaccess.py)
- 方式：2023-2025 抓取 CVF OpenAccess 列表页；2026 在 OpenAccess 发布前先抓取 CVPR virtual 论文页。
- 年份：2023-2026。
- 已验证字段：`title`、`authors`、`abstract`、`publication_date`、`detail_url`。2026 virtual 当前没有稳定 PDF 链接。
- 当前缺口：2026 PDF、DOI、机构；待 CVF OpenAccess 发布后可切回 OpenAccess 路径补 PDF。

### EMNLP Main

- source_id: `emnlp_main`
- crawler: [aclanthology.py](../app/crawlers/parsers/aclanthology.py)
- 方式：抓取 ACL Anthology `2023/2024/2025.emnlp-main.bib`。
- 年份：2023-2025。
- 已验证字段：`title`、`authors`、`publication_date`、`detail_url`、`pdf_url`、`doi`。
- 当前缺口：摘要、部分作者、机构。

## 后续补全优先级

1. `iccv`、`emnlp_main`：补 detail 页摘要。
2. `jmlr`、`tmlr`、`icml`、`iccv`：用 OpenAlex/Crossref 补 DOI。
3. 全部新增源：用 OpenAlex、OpenReview profile、PDF 首页文本补机构。
4. 如继续扩展顶刊，可优先评估 `TPAMI`、`IJCV`、`AIJ` 的 OpenAlex/Crossref metadata-only 路径，再决定是否写 publisher parser。
