# Paper Release Monitor Design

**Background**

当前论文仓已经覆盖一批 AI 顶刊顶会，但 2025/2026 的状态需要区分三件事：

1. 官方已发布，且已经完整入库
2. 官方还未发布，因此未入库不是代码问题
3. 官方已发布，但库内缺失或数量不一致，这属于代码或配置问题

用户要求文档和脚本给出直白结论，尤其是 2026 年未入库时要明确说明是“未发布”还是“代码问题”。

**Scope**

- 新增一个可独立运行的监测脚本，放在 `scripts/crawl/`
- 监测 `sources/paper/top_conference_papers.yaml` 中当前论文仓使用的顶刊顶会 source
- 默认覆盖 `2025` 和 `2026`
- 更新现有论文仓文档，记录 2025/2026 结论和脚本用法
- 不改动现有爬虫抓取逻辑，不在本轮直接修补新的 parser 行为

**Approach**

采用显式 source 规则，而不是做抽象化规则引擎。原因是各官方站点差异很大：

- ACL / EMNLP: ACL Anthology BibTeX volume
- IJCAI: proceedings HTML
- CVPR / ICCV: CVF OpenAccess 或 virtual 页
- ECCV: ECVA virtual JSON 或历史 papers index
- ICLR / ICML / TMLR: OpenReview API 或 virtual JSON
- JMLR / JAIR: 官方 index / OAI
- AAAI: OJS issue archive / issue pages

这类规则天然是站点特定逻辑，强行抽象会增加复杂度并削弱可维护性。

**Output Model**

脚本按 `source_id + year` 输出一行，字段至少包括：

- `source_id`
- `venue`
- `year`
- `db_count`
- `official_count`
- `official_status`
- `verdict`
- `reason`
- `official_evidence_url`

判定口径固定如下：

- `published_and_in_db`
  - 官方已发布
  - 若能拿到 `official_count`，则要求 `db_count == official_count`
  - 若拿不到精确条数，则要求 `db_count > 0`
- `not_published_yet`
  - 官方尚未发布论文数据
- `published_but_missing_in_db`
  - 官方已发布，但 `db_count == 0`
  - 或者 `official_count` 已知且 `db_count != official_count`
- `not_applicable_year`
  - 该 venue 本年没有对应会次，例如 `ECCV 2025`、`ICCV 2026`

**Reuse Strategy**

监测脚本优先复用已有 parser 的解析函数，避免出现“监测逻辑”和“爬虫逻辑”各自维护不同 HTML 解析规则的问题。

计划复用：

- `ACLAnthologyCrawler._parse_bib`
- `IJCAIProceedingsCrawler._parse_page`
- `CVFCrawler._parse_rows`
- `CVFCrawler._parse_virtual_rows`
- `ECVACrawler._extract_year_block`
- `ECVACrawler._parse_year_block`
- `JMLRPapersCrawler._parse_rows`
- `JAIROAICrawler._parse_page`
- `NeurIPSCrawler` 使用的 `_PAPER_ROW_RE`

**Testing**

本轮只补最小、稳定的单元测试，不做重网络集成测试。测试重点放在纯判定逻辑：

- 官方未发布 -> `not_published_yet`
- 官方已发布且条数一致 -> `published_and_in_db`
- 官方已发布且库内为空 -> `published_but_missing_in_db`
- 官方已发布但条数不一致 -> `published_but_missing_in_db`
- 本年不适用 -> `not_applicable_year`

**Documentation**

更新 `docs/paper_source_crawlers.md`：

- 增加“2025/2026 发布监测结论”
- 明确说明 2025 当前适用会刊均已入库
- 明确说明 2026 中哪些 source 未入库是因为官方未发布
- 增加监测脚本用法

**Risks**

- 个别官方页面 headline paper count 可能包含 front matter，不等于论文条数；因此优先使用 parser 可复用的条目解析结果，而不是页面 headline 数字
- rolling journal 的 2026 数据会持续增长，因此脚本输出应基于运行时实时查询，不把静态数字硬编码进逻辑
