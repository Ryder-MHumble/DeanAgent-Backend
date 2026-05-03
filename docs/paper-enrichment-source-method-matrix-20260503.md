# Papers 数据源补全方法矩阵与限流阈值（2026-05-03）

## 口径

本文基于当前 `papers` 表真实数据生成，覆盖表内全部 `source_id / venue` 组合。当前总量为 `50,835` 条。

当前结论：

- `authors` 作者名单字段：`50,835 / 50,835` 已有，当前不存在作者名单缺失问题。
- `affiliations` 作者机构字段：`20,296 / 50,835` 已有，机构仍是最大缺口。
- `author_descriptions / author_experiences` 作者画像字段：主要依赖 OpenReview profile，目前只有 ICLR 基本可补。

---

## 全量 Source/Venue 状态

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
