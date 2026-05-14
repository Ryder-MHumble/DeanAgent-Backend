# AI 顶刊顶会论文仓信源爬虫说明

> 最后更新: 2026-05-14

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

监测入口：

```bash
.venv/bin/python scripts/crawl/monitor_paper_release_status.py
.venv/bin/python scripts/crawl/monitor_paper_release_status.py --year 2026
.venv/bin/python scripts/crawl/monitor_paper_release_status.py --year 2025 --source neurips --source icml
```

脚本当前固定输出五类判定：

- `published_and_in_db`
- `not_published_yet`
- `published_but_missing_in_db`
- `not_applicable_year`
- `probe_failed`

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

## 表格版快照

以下表格按 2026-05-14 的 `papers` 表实时数据整理，版式对应当前对外汇报截图。

口径说明：

- `ACL` 行为 `acl_long + acl_short` 聚合
- `年份范围` 和 `年份数` 按当前 source 配置口径整理
- 年份列固定展示 `2026 / 2025 / 2024 / 2023`，更早年份只计入 `论文数`
- `作者 / 摘要 / 机构 / 详情页 / PDF / DOI` 为该 source 内对应字段非空覆盖率
- `核心完整度` 当前明确按 `(作者 + 摘要 + 机构 + 详情页) / 4` 计算，不把 `PDF / DOI` 纳入核心口径

| 顶刊/顶会 | 年份范围 | 年份数 | 论文数 | 2026 | 2025 | 2024 | 2023 | 作者 | 摘要 | 机构 | 详情页 | PDF | DOI | 核心完整度 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ICML | 2023-2026 | 4 | 14,047 | 6,352 | 3,257 | 2,610 | 1,828 | 100.0% | 100.0% | 98.6% | 100.0% | 54.8% | 0.0% | 99.7% |
| CVPR | 2023-2026 | 4 | 12,010 | 4,070 | 2,871 | 2,716 | 2,353 | 100.0% | 100.0% | 62.2% | 100.0% | 66.1% | 15.5% | 90.5% |
| ICLR | 2024-2026 | 3 | 11,315 | 5,352 | 3,703 | 2,260 | 0 | 100.0% | 100.0% | 88.2% | 100.0% | 100.0% | 0.2% | 97.0% |
| AAAI | 2024-2026 | 3 | 11,271 | 4,920 | 3,486 | 2,865 | 0 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| NeurIPS | 2022-2026 | 5 | 16,205 | 0 | 5,823 | 4,493 | 3,218 | 98.0% | 61.2% | 48.8% | 100.0% | 0.0% | 31.3% | 77.0% |
| ICCV | 2023-2025 | 2 | 4,857 | 0 | 2,701 | 0 | 2,156 | 100.0% | 99.1% | 97.6% | 100.0% | 100.0% | 20.3% | 99.2% |
| EMNLP | 2023-2025 | 3 | 4,124 | 0 | 1,809 | 1,268 | 1,047 | 100.0% | 94.5% | 90.2% | 100.0% | 100.0% | 99.9% | 96.2% |
| ECCV | 2022-2024 | 2 | 3,950 | 0 | 0 | 2,386 | 0 | 100.0% | 100.0% | 91.4% | 100.0% | 100.0% | 100.0% | 97.8% |
| TMLR | 2023-2026 | 4 | 3,659 | 661 | 1,432 | 955 | 611 | 100.0% | 100.0% | 90.7% | 100.0% | 100.0% | 0.0% | 97.7% |
| IJCAI | 2023-2025 | 3 | 2,701 | 0 | 1,014 | 1,048 | 639 | 100.0% | 100.0% | 97.6% | 100.0% | 100.0% | 100.0% | 99.4% |
| ACL | 2024-2025 | 2 | 2,639 | 0 | 1,699 | 940 | 0 | 100.0% | 100.0% | 88.6% | 100.0% | 100.0% | 100.0% | 97.2% |
| JMLR | 2023-2026 | 4 | 1,180 | 50 | 308 | 421 | 401 | 100.0% | 100.0% | 96.6% | 100.0% | 100.0% | 0.2% | 99.2% |
| JAIR | 2023-2026 | 4 | 385 | 48 | 132 | 105 | 100 | 100.0% | 100.0% | 86.0% | 100.0% | 100.0% | 100.0% | 96.5% |

OpenReview 作者侧汇总见：

- [paper-author-enrichment-status-report-20260430.md](paper-author-enrichment-status-report-20260430.md)

## 2025/2026 发布监测结论

以下结论来自 2026-05-14 对 `papers` 表与官方站点的核对。

### 2025

结论先说清楚：除 `AAAI` 因官方 OJS 探测不稳定、暂未拿到完整 official count 外，`2025` 已能核实的顶刊顶会 source 现在都已对齐。

- 已确认和官方条数一致：`acl_long`、`acl_short`、`cvpr`、`emnlp_main`、`iccv`、`iclr`、`icml`、`ijcai`、`jair`、`jmlr`、`neurips`、`tmlr`
- 已发布但本次官方探测未拿到完整 official count：`aaai`
- 本年不适用：`eccv`

| source_id | 2025 db_count | 官方情况 | 监测结论 |
|---|---:|---|---|
| `aaai` | 3486 | AAAI OJS 已发布；本次 28 个 issue 中 1 个可达、27 个探测失败，未拿到完整 official count | `published_and_in_db`（仅确认已发布和已入库，仍建议复核） |
| `acl_long` | 1602 | ACL Anthology `2025.acl-long.bib` = 1602 | `published_and_in_db` |
| `acl_short` | 97 | ACL Anthology `2025.acl-short.bib` = 97 | `published_and_in_db` |
| `cvpr` | 2871 | CVPR OpenAccess = 2871 | `published_and_in_db` |
| `eccv` | 0 | ECCV 是双年会，2025 无会次 | `not_applicable_year` |
| `emnlp_main` | 1809 | ACL Anthology `2025.emnlp-main.bib` = 1809 | `published_and_in_db` |
| `iccv` | 2701 | ICCV OpenAccess = 2701 | `published_and_in_db` |
| `iclr` | 3703 | OpenReview `ICLR.cc/2025/Conference` = 3703 | `published_and_in_db` |
| `icml` | 3257 | OpenReview `ICML.cc/2025/Conference` = 3257 | `published_and_in_db` |
| `ijcai` | 1014 | `https://www.ijcai.org/proceedings/2025/` 解析出 1014 篇 Main Track | `published_and_in_db` |
| `jair` | 132 | JAIR OAI = 132 | `published_and_in_db` |
| `jmlr` | 308 | JMLR `v26` = 308 | `published_and_in_db` |
| `neurips` | 5823 | NeurIPS proceedings 2025 = 5823 | `published_and_in_db` |
| `tmlr` | 1432 | TMLR OpenReview 2025 = 1432 | `published_and_in_db` |

需要明确写结论的修正项：

- `ICML 2025` 现在确认不是漏抓。之前的误差来自监测口径把 `Position Paper Track` 和 `Retracted_Acceptance` 混进了主会统计；按 OpenReview 主会 venue `ICML.cc/2025/Conference` 核对后，官方值就是 `3257`，库里也是 `3257`。
- `IJCAI 2025` 之前差 `1` 不是漏抓，而是库里多了一条历史残留 `2025/1281`；清理后官方 Main Track `1014` 和库里 `1014` 已对齐。

### 2026

`2026` 的情况现在可以拆成四类：

- 没爬到，是因为官方还没发布：`acl_long`、`acl_short`、`emnlp_main`、`ijcai`、`neurips`、`eccv`
- 已发布且已对齐：`cvpr`、`iclr`、`icml`、`jair`、`jmlr`、`tmlr`
- 已发布但官方站不稳定，本次只确认“已发布”，未拿到完整 official count：`aaai`
- 本年不适用：`iccv`

| source_id | 2026 db_count | 官方情况 | 监测结论 |
|---|---:|---|---|
| `aaai` | 4920 | AAAI OJS 已发布；本次 48 个 issue 中 20 个可达、28 个探测失败，未拿到完整 official count | `published_and_in_db`（仅确认已发布和已入库，仍建议复核） |
| `acl_long` | 0 | ACL Anthology 尚无 `2026.acl-long.bib` | `not_published_yet` |
| `acl_short` | 0 | ACL Anthology 尚无 `2026.acl-short.bib` | `not_published_yet` |
| `cvpr` | 4070 | `https://cvpr.thecvf.com/virtual/2026/papers.html` = 4070 | `published_and_in_db` |
| `eccv` | 0 | ECCV 2026 virtual JSON 当前 `count = 0` | `not_published_yet` |
| `emnlp_main` | 0 | ACL Anthology 尚无 `2026.emnlp-main.bib` | `not_published_yet` |
| `iccv` | 0 | ICCV 是奇数年会，2026 无会次 | `not_applicable_year` |
| `iclr` | 5352 | OpenReview `ICLR.cc/2026/Conference` = 5352 | `published_and_in_db` |
| `icml` | 6352 | `https://icml.cc/static/virtual/data/icml-2026-orals-posters.json` 过滤后主会记录 = 6352 | `published_and_in_db` |
| `ijcai` | 0 | `https://www.ijcai.org/proceedings/2026/` 当前 404；important dates 仍在 camera-ready 阶段 | `not_published_yet` |
| `jair` | 48 | JAIR OAI = 48 | `published_and_in_db` |
| `jmlr` | 50 | JMLR `v27` = 50 | `published_and_in_db` |
| `neurips` | 0 | `https://papers.nips.cc/paper_files/paper/2026` 不可用；virtual JSON `count = 0`，abstracts JSON = 404 | `not_published_yet` |
| `tmlr` | 661 | TMLR OpenReview 2026 = 661 | `published_and_in_db` |

需要明确写结论的修正项：

- `ACL 2026` 没爬到，是因为 2026 卷还没发布。
- `EMNLP 2026` 没爬到，是因为 2026 卷还没发布。
- `IJCAI 2026` 没爬到，是因为 proceedings 还没发布。
- `NeurIPS 2026` 没爬到，是因为官方 proceedings 和 virtual abstracts 还没发布。
- `ECCV 2026` 没爬到，是因为 virtual JSON 还没放出论文数据。
- `ICML 2026` 现在确认不是 `6567` 条主会论文。virtual JSON 原始记录里混有 `215` 条 `Position:` special track；清理后主会 official count 是 `6352`，库里也已按同口径对齐到 `6352`。
- `TMLR 2026` 之前的缺口已经补齐；当前官方 `661`，库里 `661`。

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
- 方式：优先抓取 OpenReview `ICML.cc/{year}/Conference`；2026 主会 note 对 guest 不可见时，退到 ICML virtual JSON。
- 年份：2023-2026。2026 当前走 ICML virtual JSON，且会过滤 `Position:` special track。
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
