# 顶会论文信息补全方法适配结论（2026-05-03）

## 目的

沉淀当前 `papers` 库在 `CVPR / ECCV / NeurIPS / ACL / IJCAI` 这几类顶会论文上的信息补全经验，明确：

- 哪些会议适合用哪些方法补全
- 每种方法更适合补哪些字段
- 哪些方法不适合继续投入
- `PDF 首页解析` 是否值得作为兜底链路

本文基于 2026-05-03 的真实抽样验证与既有批跑结果，不是理论推测。

---

## 结论摘要

### 总体策略

对这几类顶会论文，当前最合理的补全优先级是：

1. `OpenAlex`
2. `详情页 HTML 解析`
3. `PDF 首页文本解析`
4. `MinerU / OCR 类工具` 仅作保底

### 核心判断

- `OpenReview` 不适合这批会议作为主路径
  - 当前库中 `CVPR / ECCV / NeurIPS / ACL / IJCAI` 的 `detail_url / pdf_url` 基本都不是 `openreview.net`
  - 因此无法稳定拿到 profile，也无法补全作者简介、教育经历等画像字段
- `浏览器自动化工具` 不是首选
  - 这些站点多数是静态页
  - 直接请求 `HTML / PDF` 的成本更低，且不损失关键数据
- `PDF 首页解析` 很值得接入
  - 抽样中 `CVPR / ECCV / NeurIPS / ACL / IJCAI` 的 PDF 首页都稳定出现作者与机构信息
  - 当前本地 `pypdf` 已足以处理这批 born-digital PDF
- `MinerU` 不应作为主路径
  - 当前环境未安装 `mineru / magic-pdf`
  - 且这批 PDF 并非扫描件，`pypdf` 即可满足首页机构提取需求

---

## 环境与验证前提

### 当前本地可用能力

- 已安装：
  - `pypdf`
- 当前未安装：
  - `mineru`
  - `magic-pdf`
  - `pdfplumber`
  - `fitz / pymupdf`

### 当前已知链路

现有脚本 [scripts/crawl/enrich_paper_metadata.py](/home/ubuntu/workspace/DeanAgent-Backend/scripts/crawl/enrich_paper_metadata.py) 已具备：

- `OpenAlex` 补全
- `OpenReview` 补全
- `详情页 HTML` 解析补全
- `arXiv` 补全

当前缺的是：

- `PDF 首页作者/机构提取` 兜底链路

---

## 真实验证范围

本次验证面向以下会议：

- `CVPR`
- `ECCV`
- `NeurIPS`
- `ACL Long`
- `IJCAI`

验证方式包括：

1. 针对缺机构论文抽样
2. 分别测试 `OpenAlex`
3. 测试详情页 `HTML`
4. 测试 `PDF 首页文本` 可读性与机构信号
5. 结合既有批跑日志判断真实全量收益

---

## 分会议结论

### 1. CVPR

#### 适合的方法

- `OpenAlex`：可补部分机构、作者、部分 arXiv 信息
- `HTML 详情页`：可补作者、摘要、arXiv/PDF 链接
- `PDF 首页文本`：适合补机构

#### 不适合的方法

- `OpenReview`：无入口，不适用
- `作者简介/教育经历`：当前低成本路径拿不到

#### 真实验证结论

- 小样本中，`OpenAlex` 对机构命中中等
- `HTML` 可稳定拿作者，但不提供机构
- `PDF 首页` 中机构行和邮箱都很清晰

#### 建议策略

1. 先跑 `OpenAlex`
2. 再跑 `HTML`
3. 机构仍缺失时，进入 `PDF 首页兜底`

---

### 2. ECCV

#### 适合的方法

- `OpenAlex`：当前最强主路径之一，可补机构和作者
- `PDF 首页文本`：适合做机构兜底

#### 一般的方法

- `HTML 详情页`：有详情页，但机构价值低

#### 不适合的方法

- `OpenReview`
- `作者简介/教育经历`

#### 真实验证结论

- 小样本中 `OpenAlex` 对机构命中最好
- 详情页基本拿不到机构
- PDF 首页机构编号和单位列表很清晰

#### 建议策略

1. 先跑 `OpenAlex`
2. 若机构仍缺，则走 `PDF 首页兜底`
3. `HTML` 仅保留为辅助页解析，不作为机构主路径

---

### 3. NeurIPS

#### 适合的方法

- `HTML 详情页`：可补作者、摘要、`citation_pdf_url`
- `PDF 首页文本`：机构主路径
- `OpenAlex`：可补作者、DOI，但机构效果弱

#### 不适合的方法

- `OpenReview`
- `作者简介/教育经历`

#### 真实验证结论

- 小样本中 `OpenAlex` 对机构命中接近无效
- 但 `HTML` 可以稳定给出作者和 PDF 链接
- `PDF 首页` 中机构信息清楚，适合主兜底
- 既有全量批跑中，NeurIPS 的 `OpenAlex` 机构增量也很低

#### 建议策略

1. 先解析 `HTML`，拿作者、摘要、PDF URL
2. 再尝试 `OpenAlex`
3. 机构仍缺时，直接进入 `PDF 首页解析`

---

### 4. ACL Long

#### 适合的方法

- `HTML 详情页`：可补作者、DOI、PDF 链接
- `PDF 首页文本`：机构主路径

#### 不适合的方法

- `OpenAlex`：机构收益弱
- `OpenReview`
- `作者简介/教育经历`

#### 真实验证结论

- `HTML` 页面作者信息完整，但机构不在 meta 中
- `OpenAlex` 基本不解决机构问题
- `PDF 首页` 可直接抽到符号映射机构信息

#### 建议策略

1. 先跑 `HTML`
2. 再尝试 `OpenAlex`
3. 对机构字段直接以 `PDF 首页解析` 为主兜底

---

### 5. IJCAI

#### 适合的方法

- `HTML 详情页`：可补作者、摘要、PDF 链接
- `PDF 首页文本`：机构主路径
- `OpenAlex`：可作为前置尝试

#### 不适合的方法

- `OpenReview`
- `作者简介/教育经历`

#### 真实验证结论

- 抽样里新年份论文 `OpenAlex` 可命中部分机构
- 但既有全量批跑里，机构真实增量并不高
- `PDF 首页` 稳定含机构与邮箱

#### 建议策略

1. 先跑 `HTML`
2. 再试 `OpenAlex`
3. 机构缺失时，以 `PDF 首页解析` 作为兜底主路径

---

## 方法级别结论

### OpenAlex

#### 适合补全的字段

- `authors`
- `affiliations`
- `doi`
- `arxiv_id`
- 部分 `abstract`

#### 最适合的会议

- `ECCV`
- `CVPR`
- `IJCAI`（作为尝试路径）

#### 较弱或不适合作为机构主路径的会议

- `NeurIPS`
- `ACL`

#### 结论

`OpenAlex` 应保留为第一优先级，因为成本最低，但不能假设它能解决全部顶会的机构缺口。

---

### 详情页 HTML 解析

#### 适合补全的字段

- `authors`
- `abstract`
- `doi`
- `pdf_url`
- 部分 `arxiv_id`

#### 对机构字段的能力

- 普遍偏弱
- 这批会议详情页中，机构通常不在标准 meta 中

#### 结论

`HTML` 解析是非常合适的中间层，但主要负责“补齐基础元数据”，不应被当作机构主路径。

---

### PDF 首页文本解析

#### 适合补全的字段

- `affiliations`
- 部分作者与机构的顺序映射
- 邮箱辅助机构识别

#### 当前适配性

对以下会议都值得接入：

- `CVPR`
- `ECCV`
- `NeurIPS`
- `ACL`
- `IJCAI`

#### 优势

- 机构通常就在首页标题下方
- 不依赖外部学术索引质量
- 对顶会论文的 born-digital PDF 很有效

#### 风险

- 不同会议首页作者-机构排版风格不完全一致
- 需要做一定的规则化抽取，而非仅靠裸文本

#### 结论

`PDF 首页解析` 应作为这批顶会的标准兜底链路，而不是临时尝试手段。

---

### MinerU / OCR 类工具

#### 当前判断

- 这批论文暂时不适合作为主路径
- 仅在以下情况再考虑：
  - PDF 首页面文本抽不出来
  - PDF 为扫描件
  - 版式异常导致普通文本提取失败

#### 结论

在当前这批顶会论文上，`MinerU` 是保底工具，不是第一优先级。

---

### OpenReview

#### 当前判断

- 对 `CVPR / ECCV / NeurIPS / ACL / IJCAI` 这一批并不适合作为主路径
- 根因不是 API 本身弱，而是当前库里这些 source 缺少 `openreview.net` 入口

#### 能补什么

如果有 `openreview forum/profile`，理论上可补：

- `affiliations`
- `author_descriptions`
- `author_experiences`
- `profile_flags`

#### 当前限制

- 这批论文没有稳定入口
- 无法低成本映射到 profile

#### 结论

对这几类顶会，当前应将 `OpenReview` 视为基本不适用路径。

---

## 作者简介 / 教育经历字段结论

### 当前现实情况

对 `CVPR / ECCV / NeurIPS / ACL / IJCAI` 这批论文：

- `OpenAlex` 不提供可直接落库的作者简介/教育经历
- `HTML` 详情页没有这类信息
- `PDF 首页` 也没有稳定的人物画像信息
- `OpenReview` 因入口缺失，无法低成本触达 profile

### 结论

这批会议论文当前**不适合**用低成本链路补全以下字段：

- `author_descriptions`
- `author_experiences`

如果后续确实要做，只能单独建设“作者级 profile 抓取链路”，不应混入当前的论文元数据补全过程。

---

## 推荐的正式补全策略

### 会议级推荐

| 会议 | 推荐主路径 | 推荐兜底 |
|---|---|---|
| CVPR | OpenAlex + HTML | PDF 首页 |
| ECCV | OpenAlex | PDF 首页 |
| NeurIPS | HTML + OpenAlex | PDF 首页 |
| ACL | HTML | PDF 首页 |
| IJCAI | HTML + OpenAlex | PDF 首页 |

### 字段级推荐

| 字段 | 推荐来源 |
|---|---|
| `authors` | HTML / OpenAlex |
| `abstract` | HTML / OpenAlex / arXiv |
| `doi` | OpenAlex / HTML |
| `arxiv_id` | OpenAlex / HTML / arXiv |
| `affiliations` | OpenAlex，失败后 PDF 首页 |
| `author_descriptions` | 当前这批会议不建议继续投入 |
| `author_experiences` | 当前这批会议不建议继续投入 |

---

## 后续实现建议

### 建议尽快落地

在现有 [scripts/crawl/enrich_paper_metadata.py](/home/ubuntu/workspace/DeanAgent-Backend/scripts/crawl/enrich_paper_metadata.py) 中增加：

1. `PDF 首页文本解析` 兜底
2. 仅在 `OpenAlex + HTML` 后机构仍缺失时触发
3. 只先覆盖：
   - `CVPR`
   - `ECCV`
   - `NeurIPS`
   - `ACL`
   - `IJCAI`

### 不建议现在做的事

- 不要优先接 `MinerU`
- 不要优先接浏览器自动化
- 不要为这批会议继续强行跑 `OpenReview` 作者画像链路

---

## 一句话结论

对 `CVPR / ECCV / NeurIPS / ACL / IJCAI` 这批顶会论文，当前最低成本且最有效的策略是：

**先用 `OpenAlex + HTML` 补基础元数据，再用 `PDF 首页文本` 兜底机构；作者简介和教育经历暂不适合在这批数据上继续投入。**
