# Papers 数据源补全方法矩阵与限流阈值（2026-05-03）

## 当前口径

本文基于 `papers` 表真实数据生成，覆盖表内全部 `source_id / venue` 组合。

截至 2026-05-06 本轮增量任务启动后查询，当前总量为 `71,969` 条。

当前结论：

- `authors` 作者名单字段：`71,963 / 71,969` 已有，作者名单基本补齐，仅剩 `6` 条异常。
- `affiliations` 作者机构字段：`58,508 / 71,969` 已有，机构仍是最大缺口，剩余约 `13,461` 条。
- `abstract` 摘要字段：`65,620 / 71,969` 已有。
- `doi` 字段：`37,119 / 71,969` 已有。
- `arxiv_id` 字段：`8,254 / 71,969` 已有。
- `author_descriptions / author_experiences` 作者画像字段：`13,315 / 71,969` 已有，主要依赖 OpenReview profile；非 OpenReview source 不应承诺大规模补齐。

2026-05-06 当前正在继续执行低 QPS 补全批次：

| 批次 | 目标 | 数量 | 当前方法 | 备注 |
|---|---|---:|---|---|
| `cvpr_missing_aff_20260506` | CVPR 缺机构 | 4,412 | CVF HTML + OpenAlex + PDF 首页 | `pdf_qps=0.15`，运行中 |
| `neurips_missing_aff_20260506` | NeurIPS 缺机构 | 2,112 | NeurIPS HTML + OpenAlex + PDF 首页 | `pdf_qps=0.15`，运行中 |
| `iccv_missing_aff_20260506` | ICCV 缺机构 | 1,034 | CVF HTML + OpenAlex + PDF 首页 | `pdf_qps=0.15`，运行中 |
| `acl_emnlp_missing_aff_20260506` | ACL/EMNLP 缺机构 | 1,275 | ACL Anthology + PDF 首页 + OpenAlex | `pdf_qps=0.15`，运行中 |
| `jair_missing_aff_20260506` | JAIR 缺机构 | 337 | OpenAlex + PDF 首页 | 已完成，OpenAlex 补出主要增量 |
| `aaai_missing_abs_doi_20260506` | AAAI 缺摘要/DOI | 985 | OpenAlex | 已完成，补摘要/DOI `424` 条 |
| `openalex_source_missing_core_20260506` | OpenAlex source 缺核心字段 | 5,725 | OpenAlex by title/DOI | 运行中 |
| `openreview_profile_remaining_20260506` | ICLR/ICML/TMLR 剩余 profile 缺口 | 3,357 | OpenReview note/profile + OpenAlex | `openreview_qps=0.8`，查全部作者 |
| `eccv_ijcai_jmlr_missing_aff_20260506` | ECCV/IJCAI/JMLR 缺机构 | 521 | 官方 HTML + OpenAlex + PDF 首页 | `pdf_qps=0.1`，运行中 |

---

## 全量 Source/Venue 状态基线快照

| source_id | venue | total | 有作者 | 有机构 | 有作者画像 | detail_url | pdf_url | OpenReview URL | 年份 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| aaai | AAAI | 11271 | 11271 | 11123 | 0 | 11271 | 11271 | 0 | 2024-2026 |
| neurips | NeurIPS | 9923 | 9923 | 45 | 0 | 9923 | 0 | 0 | 2022-2024 |
| cvpr | CVPR | 7940 | 7940 | 1148 | 0 | 7940 | 7940 | 0 | 2023-2025 |
| openalex |  | 6445 | 6445 | 0 | 0 | 0 | 0 | 0 | 未知 |
| iclr | ICLR | 5963 | 5963 | 5939 | 5937 | 5963 | 5963 | 5963 | 2024-2025 |
| eccv | ECCV | 3950 | 3950 | 1309 | 0 | 3950 | 3950 | 0 | 2022-2024 |
| ijcai | IJCAI | 2702 | 2702 | 625 | 0 | 2702 | 2702 | 0 | 2023-2025 |
| acl_long | ACL | 2466 | 2466 | 51 | 0 | 2466 | 2466 | 0 | 2024-2025 |
| acl_short | ACL | 173 | 173 | 56 | 0 | 173 | 173 | 0 | 2024-2025 |
| paper_service_6db25e4012_source | ICLR | 2 | 2 | 0 | 0 | 2 | 0 | 0 | 2024 |

---

## 方法优先级总览

| 方法 | 成本 | 适合字段 | 不适合字段 | 当前角色 |
|---|---:|---|---|---|
| OpenAlex API | 低 | 作者、机构、DOI、arXiv、摘要 | 作者简介、教育经历 | 第一优先级通用补全 |
| OpenReview API | 中 | 机构、作者简介、教育经历、学生/华人标记 | 非 OpenReview 会议 | ICLR 主路径 |
| arXiv API | 低 | 摘要、arXiv ID、DOI、作者 | 机构、作者画像 | 元数据补充 |
| 详情页 HTML | 低 | 作者、摘要、DOI、PDF URL、arXiv URL | 大多数会议的机构 | 低成本基础元数据补齐 |
| PDF 首页文本 | 中 | 机构、邮箱辅助识别 | 作者简介、教育经历 | 顶会机构兜底 |
| 浏览器自动化 | 高 | 动态页面、反爬验证后的页面抓取 | 静态 HTML/PDF 页面 | 当前仅保底 |
| MinerU/OCR | 本地高 CPU | 扫描件、复杂版式 PDF | 常规 born-digital PDF | 最后保底 |

---

## Source/Venue 方法分类

### AAAI

推荐顺序：

1. `OpenAlex`
2. `AAAI OJS HTML`
3. `PDF 首页`

字段判断：

- 机构：当前已覆盖很高，仅剩少量缺口；优先 OpenAlex/HTML，PDF 可兜底。
- 摘要/DOI：OJS HTML 和 OpenAlex 可补。
- 作者画像：当前不建议投入，缺少 OpenReview profile 入口。

限流阈值：

- `ojs.aaai.org` HTML：`0.3-0.5 req/s`，并发 `1-2`
- PDF：`0.2-0.3 req/s`，并发 `1`
- OpenAlex：全局 `3-5 req/s`，并发 `4-6`

封禁风险：

- OJS 类站点对高频 PDF/HTML 抓取更敏感，出现 `429/403/5xx` 连续 3 次应暂停该 host `10-30 min`。

---

### NeurIPS

推荐顺序：

1. `NeurIPS HTML`
2. `OpenAlex`
3. `PDF 首页`

字段判断：

- 作者/摘要/PDF URL：HTML 稳定。
- 机构：OpenAlex 很弱，PDF 首页是主要兜底。
- DOI：HTML/OpenAlex 均可尝试。
- 作者画像：当前不建议投入。

限流阈值：

- `papers.nips.cc / proceedings.neurips.cc` HTML：`0.5 req/s`，并发 `1-2`
- PDF：`0.2-0.3 req/s`，并发 `1`
- OpenAlex：全局 `3-5 req/s`

封禁风险：

- NeurIPS 静态页稳定，但 PDF 文件量大。批量 PDF 建议单独慢跑，连续 `429/403` 或连接断开率超过 `5%` 时降到 `0.1 req/s`。

---

### CVPR

推荐顺序：

1. `OpenAlex`
2. `CVF OpenAccess HTML`
3. `PDF 首页`

字段判断：

- 作者/摘要/arXiv：CVF HTML 稳定。
- 机构：OpenAlex 有中等收益；剩余缺口适合 PDF 首页。
- 作者画像：当前不建议投入。

限流阈值：

- `openaccess.thecvf.com` HTML：`0.5-1 req/s`，并发 `2`
- PDF：`0.2-0.3 req/s`，并发 `1`
- OpenAlex：全局 `3-5 req/s`

封禁风险：

- CVF 静态页可承受适度请求；PDF 应慢跑。若 `timeout/503` 连续出现，暂停 host `10 min`。

---

### openalex

推荐顺序：

1. `OpenAlex by DOI/title`
2. 不适用 HTML/PDF，除非后续能补回原始 landing page

字段判断：

- 这批来源本身是 OpenAlex 导入，但当前机构为空，说明导入链路可能未落 authorships institutions。
- 可用标题/DOI 重新查 OpenAlex 补机构和摘要。
- 没有 detail/pdf URL，不适合 HTML/PDF。

限流阈值：

- OpenAlex：全局 `3-5 req/s`，并发 `4-6`
- 遇到 `429`：指数退避，最低降到 `1 req/s`

封禁风险：

- OpenAlex 相对友好，但仍应带 User-Agent/mailto，避免无头高并发。

---

### ICLR

推荐顺序：

1. `OpenReview API`
2. `OpenAlex`
3. `arXiv API`

字段判断：

- 机构：OpenReview profile 主路径，当前已基本补满。
- 作者简介/教育经历：只有 ICLR 当前适合大规模补。
- 摘要/作者：OpenReview note 稳定。

限流阈值：

- OpenReview profile：`0.8 req/s`，并发 `1` 的实际 QPS 约束，profile cache 必须开启。
- OpenReview note：可同队列处理，不要超过 `1 req/s`。
- OpenAlex：全局 `3-5 req/s`。

封禁风险：

- OpenReview 明显有 QPS 敏感性。连续 `429/403/5xx` 3 次应暂停 `15-30 min`，恢复后降到 `0.3-0.5 req/s`。

---

### ECCV

推荐顺序：

1. `OpenAlex`
2. `ECVA HTML`
3. `PDF 首页`

字段判断：

- 机构：OpenAlex 是主路径，PDF 首页兜底效果强。
- HTML：可保留为基础元数据路径，但机构收益低。
- 作者画像：当前不建议投入。

限流阈值：

- `www.ecva.net` HTML：`0.5 req/s`，并发 `1-2`
- PDF：`0.2-0.3 req/s`，并发 `1`
- OpenAlex：全局 `3-5 req/s`

封禁风险：

- ECVA PDF 链接集中，批量 PDF 下载应严格慢跑；出现连接断开时降到 `0.1 req/s`。

---

### IJCAI

推荐顺序：

1. `IJCAI HTML`
2. `OpenAlex`
3. `PDF 首页`

字段判断：

- 作者/摘要/PDF URL：HTML 稳定。
- 机构：OpenAlex 部分有效，但全量收益不高；PDF 首页适合作为主兜底。
- 作者画像：当前不建议投入。

限流阈值：

- `www.ijcai.org` HTML：`0.5 req/s`，并发 `1-2`
- PDF：`0.2-0.3 req/s`，并发 `1`
- OpenAlex：全局 `3-5 req/s`

封禁风险：

- IJCAI 页面结构简单，但 PDF 批量下载仍应慢跑；连续异常时暂停 `10 min`。

---

### ACL Long / ACL Short

推荐顺序：

1. `ACL Anthology HTML`
2. `PDF 首页`
3. `OpenAlex`

字段判断：

- 作者/DOI/PDF URL：HTML 稳定。
- 机构：OpenAlex 弱，PDF 首页是主路径。
- 作者画像：当前不建议投入。

限流阈值：

- `aclanthology.org` HTML：`0.5 req/s`，并发 `1-2`
- PDF：`0.2-0.3 req/s`，并发 `1`
- OpenAlex：全局 `3-5 req/s`

封禁风险：

- ACL PDF 偶发连接断开，建议用低 QPS 和重试。若断开率超过 `5%`，降到 `0.1 req/s`。

---

### paper_service_6db25e4012_source

推荐顺序：

1. 先归一化 source
2. 若能解析出 OpenReview/forum/arXiv/DOI，再进入对应链路

字段判断：

- 当前仅 2 条，属于临时来源，不适合单独建设策略。
- 可作为异常数据治理项。

限流阈值：

- 按解析出的目标站点继承阈值。

---

## 统一限流与封禁处理规则

### API 阈值

| API | 默认 QPS | 建议并发 | 触发降速条件 | 降速后 |
|---|---:|---:|---|---:|
| OpenAlex | `3-5 req/s` | `4-6` | `429` 或连续 `5xx >= 3` | `1 req/s` |
| OpenReview | `0.8 req/s` | QPS 严格串行 | `429/403/5xx >= 3` | `0.3-0.5 req/s` |
| arXiv | `0.3 req/s` | `1` | `503/429` 或超时 | `0.1 req/s` |

### 页面/PDF 阈值

| 类型 | 默认 QPS | 建议并发 | 说明 |
|---|---:|---:|---|
| HTML 静态详情页 | `0.5 req/s/host` | `1-2/host` | 优先低成本抓取 |
| PDF 首页下载 | `0.2-0.3 req/s/host` | `1/host` | 文件下载最容易触发风控 |
| 浏览器自动化 | `0.1-0.2 page/s/host` | `1 context/host` | 仅用于静态请求失败场景 |
| MinerU/OCR | 本地队列 | CPU/GPU 限制 | 不触发 IP 风控，但成本高 |

### 封 IP / 限流保护

出现以下任一情况，应认为 host 进入风险状态：

- 连续 `429` 或 `403` 达到 `3` 次
- 连续 `5xx` 达到 `5` 次
- PDF 连接断开/超时率超过 `5%`
- 单 host 平均响应时间超过正常水平 `3x`

处理策略：

1. 立即暂停该 host `10-30 min`
2. 恢复后 QPS 降低到原来的 `30%-50%`
3. PDF 下载优先降速，API 查询其次
4. 不要用浏览器自动化绕过明确的 `403/429`

---

## 当前执行建议

优先补机构缺口最大的 source：

1. `NeurIPS`：HTML + PDF 首页
2. `CVPR`：OpenAlex + HTML + PDF 首页
3. `openalex`：OpenAlex 重查
4. `ECCV`：OpenAlex + PDF 首页
5. `ACL Long/Short`：HTML + PDF 首页
6. `IJCAI`：HTML + OpenAlex + PDF 首页

当前无需继续重跑 ICLR 作者画像，除非专门处理剩余 `24-26` 条尾部异常。

---

## 2026-05-06 迭代更新

### 策略已沉淀到 YAML

本轮已将补全策略写入 source 配置，后续运行不再只依赖临时命令经验。

已更新：

- `sources/paper/top_conference_papers.yaml`
- `sources/paper/conferences.yaml`
- `sources/paper/journals.yaml`

主论文仓 `top_conference_papers.yaml` 中新增 `enrichment_profiles`，并给每个主表 source 绑定 `enrichment`：

| profile | 覆盖 source | 主路径 | 兜底 | 主要字段 |
|---|---|---|---|---|
| `openreview_profile` | `iclr`, `icml`, `tmlr` | OpenReview note/profile | OpenAlex/arXiv | 机构、作者简介、经历、profile flags |
| `cvf_pdf` | `cvpr`, `iccv` | CVF HTML + OpenAlex | PDF 首页 | 作者、摘要、机构、arXiv |
| `acl_pdf` | `acl_long`, `acl_short`, `emnlp_main` | ACL Anthology HTML | PDF 首页、OpenAlex | 作者、摘要、DOI、机构 |
| `proceedings_pdf` | `neurips`, `eccv`, `ijcai` | 官方详情页 + OpenAlex | PDF 首页 | 作者、摘要、机构、DOI/arXiv |
| `ojs_openalex` | `aaai` | AAAI OJS HTML + OpenAlex | PDF 首页 | 作者、摘要、DOI、机构 |
| `journal_pdf` | `jmlr`, `jair` | 官方 HTML + OpenAlex | PDF 首页 | 作者、摘要、DOI、机构 |

作者信号源 YAML 也新增了 `enrichment` 摘要：

- `openreview_author`：OpenReview 作者画像路径
- `acl_anthology_author`：ACL/EMNLP HTML + PDF 首页路径
- `cvf_openaccess_author`：CVF HTML + PDF 首页路径
- `dblp_author`：作者/DOI 校验，不作为机构主路径
- `arxiv_author`：摘要/arXiv/DOI 校准，不提供机构
- `semantic_scholar_author`：作者/摘要/DOI 辅助
- `academic_paper_authors`：本地结构化证据合并

### 最新字段覆盖状态

截至 2026-05-06 最新查询：

| 指标 | 数量 | 覆盖率 |
|---|---:|---:|
| 总论文 | 71,969 | 100% |
| 有作者 | 71,963 | 100.0% |
| 有机构 | 58,508 | 81.3% |
| 有摘要 | 65,620 | 91.2% |
| 有 DOI | 37,119 | 51.6% |
| 有 arXiv ID | 8,254 | 11.5% |
| 有作者简介 | 13,315 | 18.5% |
| 有作者经历 | 13,315 | 18.5% |

### 继续补全执行策略

2026-05-06 后续补全按“真实可增量”拆分：

1. OpenReview 源：`iclr / icml / tmlr`
   - 用 OpenReview note/profile 补机构、作者简介、经历、flags。
   - `openreview_qps=0.8`。
   - 抽样发现剩余长尾命中但无新增字段，因此不再盲目全量空跑。

2. CVF/ACL/Proceedings 源：`cvpr / iccv / neurips / acl_long / acl_short / emnlp_main / eccv / ijcai`
   - 官方 HTML 补作者、摘要、DOI、PDF URL、arXiv。
   - OpenAlex 补机构、摘要、DOI、arXiv。
   - PDF 首页补机构。
   - 当前执行 `pdf_qps=0.15`，低于原建议上限，优先降低封禁风险。

3. 期刊源：`jmlr / jair`
   - JMLR PDF 首页对机构有效。
   - JAIR 部分 `pdf_url` 返回 HTML 包装页，OpenAlex 已补出部分机构；剩余机构需要适配真实 PDF 下载链接或 OAI 元数据中的 affiliation 字段。

4. OpenAlex 导入源：`openalex`
   - 该 source 没有 `detail_url/pdf_url`，不能走 HTML/PDF。
   - 可继续按 title/DOI 重新查 OpenAlex，但剩余数据需要避免被“必须有 detail/pdf URL”的候选过滤排除。

### 当前仍不适合补的字段

非 OpenReview 信源的以下字段不建议继续强行补：

- `author_descriptions`
- `author_experiences`
- `profile_flags`

原因：官方 HTML、OpenAlex、arXiv、PDF 首页都不稳定提供个人履历/教育经历。继续补这类字段需要单独建设作者级 profile 抓取链路，而不是混在论文元数据补全任务中。

### 封禁与降速阈值

当前执行阈值：

| 类型 | 当前执行值 | 上限建议 |
|---|---:|---:|
| OpenReview | `0.8 req/s` | `0.8 req/s` |
| PDF 首页 | `0.1-0.15 req/s/host` | `0.2-0.3 req/s/host` |
| HTML 静态页 | 随任务并发，实际低速 | `0.5 req/s/host` |
| OpenAlex | 并发 `3` 左右 | `3-5 req/s` |

降速/暂停条件：

- 连续 `429/403 >= 3`：暂停该 host `10-30 min`
- 连续 `5xx >= 5`：暂停该 host `10 min`
- PDF 超时/断连率超过 `5%`：PDF QPS 降至 `0.05-0.1 req/s`
- 明确 `403/429` 时不使用浏览器自动化绕过
