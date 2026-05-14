# Papers 信息补全阶段汇报（2026-04-30）

## 2026-05-13 OpenReview Authors 汇总

> 本节按当前 `papers` 表中 `profile_flags / author_descriptions / author_experiences` 的实际落库结果统计，版式对应当前对外汇报截图。

口径说明：

- `已识别唯一 OpenReview Profile`：`profile_flags[].profile_id` 去重后的唯一 profile 数
- `已入库/覆盖 Profile`：至少具备 `description / experiences / institution / position / department` 之一的唯一 profile 数
- `作者画像行数`：`profile_flags` 中按论文作者展开后的总行数
- `已解析非空 profile_id`：作者画像行里 `profile_id` 非空的行数
- `当前机构 / 职位 / 部门`：按唯一 profile 统计，对应信息来自 `author_experiences` 和作者画像合并结果
- `研究方向/关键词`：当前 schema 未单列存储，因此不做百分比承诺

| 维度 | 当前进展 |
|---|---:|
| 已识别唯一 OpenReview Profile | 33,282 |
| 已入库/覆盖 Profile | 33,116，99.5% |
| 剩余待补 Profile | 166 |
| 作者画像行数 | 93,689 |
| 已解析非空 `profile_id` | 64,885 |
| 姓名/Profile URL/来源论文关联 | 100.0% |
| 当前机构 | 99.5% |
| 职位 | 99.5% |
| 部门 | 46.9% |
| 教育经历 | 99.5% |
| 研究方向/关键词 | 暂未落独立字段 |
| 个人主页/外链 | 11.9% |
| 平均关联论文数 | 1.95 篇/人 |

## 2026-05-01 进展更新

> 本节为 2026-05-01 的增量进展，保留原文档主体用于对比 2026-04-30 与 2026-05-01 的阶段变化。

### 核心变化

- `OpenAlex` 已从前一日的预算不足状态恢复，可正常返回检索结果。
- 已启动新一轮针对非 OpenReview 来源的机构补缺批次：`NeurIPS / ECCV / IJCAI / ACL long / CVPR`，并已完成 `ACL short`。
- `ICLR / OpenReview` 上一轮 `3249` 条尾部任务已跑完，当前又补起一轮剩余 `255` 条尾部缺口，仍按“全作者查询 + 0.8 req/s”执行。

### 当前全库覆盖率（2026-05-01 实时统计）

| 字段 | 已补数量 | 覆盖率 |
|---|---:|---:|
| 机构（`affiliations`） | 19181 | 37.7% |
| 摘要（`abstract`） | 43246 | 85.1% |
| DOI（`doi`） | 30553 | 60.1% |
| arXiv ID（`arxiv_id`） | 5182 | 10.2% |
| 作者简介（`author_descriptions`） | 5708 | 11.2% |
| 作者经历（`author_experiences`） | 5708 | 11.2% |
| 标记（`profile_flags`） | 5708 | 11.2% |

相较 2026-04-30 的文档基线，本轮已确认新增：

- 机构信息 `+3254`
- 摘要 `+83`
- DOI `+696`
- arXiv ID `+45`
- 作者简介 `+1867`
- 作者经历 `+1867`
- 标记 `+1866`

### 当前重点信源进度（2026-05-01 实时统计）

| source_id | 总量 | 机构 | 摘要 | DOI | arXiv ID | 作者简介 | 作者经历 | 标记 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `aaai` | 11271 | 11112 | 10128 | 10128 | 7 | 0 | 0 | 0 |
| `neurips` | 9923 | 30 | 9923 | 4629 | 3 | 0 | 0 | 0 |
| `cvpr` | 7940 | 785 | 7939 | 819 | 5117 | 0 | 0 | 0 |
| `iclr` | 5963 | 5717 | 5963 | 6 | 0 | 5708 | 5708 | 5708 |
| `eccv` | 3950 | 816 | 3950 | 3950 | 1 | 0 | 0 | 0 |
| `ijcai` | 2702 | 614 | 2702 | 2702 | 53 | 0 | 0 | 0 |
| `acl_long` | 2466 | 51 | 2466 | 2466 | 0 | 0 | 0 | 0 |
| `acl_short` | 173 | 56 | 173 | 173 | 1 | 0 | 0 | 0 |

### 当前仍在运行的批次（2026-05-01 观察值）

| 批次 | 状态 | 说明 |
|---|---|---|
| `neurips` | 运行中 | OpenAlex 恢复后补机构 |
| `eccv` | 运行中 | OpenAlex 恢复后补机构 |
| `ijcai` | 运行中 | OpenAlex 恢复后补机构 |
| `acl_long` | 运行中 | OpenAlex 恢复后补机构 |
| `cvpr` | 运行中 | OpenAlex 恢复后补机构 |
| `iclr` 尾部 255 条 | 运行中 | OpenReview 全作者 profile 精补 |

### 当前缺口判断

- 非 OpenReview 来源里，机构缺口仍主要集中在：
  - `NeurIPS`：`9893`
  - `CVPR`：`7155`
  - `ECCV`：`3134`
  - `ACL long`：`2415`
  - `IJCAI`：`2088`
- 作者画像字段仍基本集中在 `ICLR / OpenReview`，其它来源目前没有稳定作者画像信源。
- `AAAI` 机构补全已经非常高，但摘要仍有 `1143` 条缺口，机构还有 `159` 条尾差。

> 统计范围：`papers` 表全量数据
> 统计口径：以下覆盖率均按 `papers` 表总量计算；运行状态为生成时观察结果
> 设计方案：`OpenReview API + arXiv API + OpenAlex API`
> 本轮实际启用路径：`OpenReview + arXiv + OpenAlex + 页面解析兜底`
> 当前不可用：`academic-monitor`（接口 404）

## 1. 执行摘要

本轮已经形成一套可运行的“多 API + 页面解析兜底”的论文信息补全机制，核心思路是：按信源分流、按字段择优、按 API 能力组合补全。当前成果已经从“补单点字段”推进到“补全库大盘”，论文级字段补全效果明显，作者画像字段则主要集中在 `ICLR / OpenReview` 体系内持续增长。

截至 `2026-05-01` 实时统计，`papers` 全量 `50835` 篇论文中：

- `abstract` 已覆盖 `43246` 篇，覆盖率 `85.1%`
- `doi` 已覆盖 `30553` 篇，覆盖率 `60.1%`
- `affiliations` 已覆盖 `19181` 篇，覆盖率 `37.7%`
- 作者画像字段 `author_descriptions / author_experiences / profile_flags` 已覆盖 `5708` 篇，覆盖率 `11.2%`

本轮最重要的现实结论有三点：

1. 论文级字段已经形成稳定增量，尤其是 `abstract` 和 `doi`，说明基础信息补齐机制已经跑通。
2. 机构字段当前仍主要由 `AAAI + ICLR` 拉动，但 `OpenAlex` 恢复后，`NeurIPS / ECCV / IJCAI / ACL / CVPR` 已开始出现新增机构覆盖。
3. 作者画像字段当前几乎全部依赖 `OpenReview`，因此虽然 `ICLR` 增长明显，但增长面仍然偏窄。

当前最主要的外部瓶颈不是代码逻辑，而是信源能力边界与配额：

- `OpenReview` 需要逐作者 profile 查询，必须按 `0.8 req/s` 限速运行。
- `OpenAlex` 已恢复可用，但对非 OpenReview 来源的机构缺口总量仍很大，需要继续跑完整批次。

建议管理层关注的决策点：

- `决策 1`：持续使用已恢复的 `OpenAlex` 配额，优先补齐非 OpenReview 来源的机构字段。
- `决策 2`：继续跑完 `ICLR / OpenReview` 剩余任务，收敛作者简介、经历、profile flags。
- `决策 3`：中期引入新增作者级数据源，降低对 OpenReview 的单点依赖。

## 2. 机制设计

### 2.1 设计目标

本轮不是只补某一个字段，而是围绕 `papers` 表中缺失的论文级信息和作者级信息，设计一套“按字段能力分工”的补全机制。

目标字段包括：

| 类型 | 字段 |
|---|---|
| 论文级字段 | `abstract`、`doi`、`arxiv_id`、`authors`、`affiliations` |
| 作者画像字段 | `author_descriptions`、`author_experiences`、`profile_flags` |

### 2.2 核心设计思路

设计原则不是“所有论文都走同一个 API”，而是“什么字段适合什么来源就走什么来源”：

- `OpenReview API`
  - 优先负责作者画像字段
  - 同时可以补部分机构信息
- `arXiv API`
  - 优先负责 arXiv 论文元数据
  - 适合补 `abstract / arxiv_id / doi`
- `OpenAlex API`
  - 理论上是最通用的论文级补全来源
  - 适合补 `abstract / doi / arxiv_id / authors / affiliations`

如果某类 API 不可用，或者信源页面自身已提供较完整的 meta 信息，则进入“页面解析兜底”流程，直接从论文源站详情页提取摘要、DOI、作者名；少数来源还能补作者机构。以上描述的是理论分工，下一节单独说明本轮真实执行路径。

### 2.3 真实执行链路

本轮真实执行机制如下：

1. 先从 `detail_url / pdf_url` 中解析可直接获得的标识符，包括 `forum_id`（OpenReview 论文 ID）、`arxiv_id`、`doi`。
2. 再根据论文所属信源和可用标识符组合补全路径：
   - 有 `forum_id`：走 `OpenReview`
   - 有 `arxiv_id`：走 `arXiv`
   - `OpenAlex` 可用时：走 DOI 或标题检索
   - 详情页属于已接入站点时：走页面解析兜底
3. 对多个来源返回结果按字段质量择优合并：
   - 摘要取更完整版本
   - 机构取覆盖人数更多的版本
   - 作者画像字段取更完整版本
4. 将结果写回 `papers`

### 2.4 本轮实际运行参数

本轮真实运行中，为了控制限流、慢连接和站点压力，采用了如下策略：

| 参数/策略 | 当前值/方式 | 目的 |
|---|---|---|
| `--max-profile-requests` | `0` | 查询全部作者，不做前 N 个截断 |
| `--openreview-qps` | `0.8` | 控制 OpenReview 速率，避免限流 |
| `--concurrency` | 页面类任务通常 `4~8` | 控制站点并发压力 |
| `--timeout` | 默认 `25s`，AAAI 尾部尝试 `8s` | 降低慢连接长尾拖累 |
| `--disable-openalex` | 仅在特定批次启用 | OpenAlex 恢复前用于绕过预算不足；恢复后已重新启用 |
| `--disable-academic-monitor` | 本轮启用 | 本地接口返回 `404`，不可用 |

## 3. 整体进度与现状

### 3.1 全库进度

当前 `papers` 表总量：`50835`。以下“已补数量”均指对应字段非空的论文行数，“覆盖率”按 `50835` 计算。

| 字段 | 已补数量 | 覆盖率 |
|---|---:|---:|
| 机构（`affiliations`） | 19181 | 37.7% |
| 摘要（`abstract`） | 43246 | 85.1% |
| DOI（`doi`） | 30553 | 60.1% |
| arXiv ID（`arxiv_id`） | 5182 | 10.2% |
| 作者简介（`author_descriptions`） | 5708 | 11.2% |
| 作者经历（`author_experiences`） | 5708 | 11.2% |
| 标记（`profile_flags`） | 5708 | 11.2% |

### 3.2 各主要信源进度

| source_id | venue | 总量 | 机构（`affiliations`） | 摘要（`abstract`） | DOI（`doi`） | arXiv ID（`arxiv_id`） | 作者简介（`author_descriptions`） | 作者经历（`author_experiences`） | 标记（`profile_flags`） |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `aaai` | AAAI | 11271 | 11112 | 10128 | 10128 | 7 | 0 | 0 | 0 |
| `neurips` | NeurIPS | 9923 | 30 | 9923 | 4629 | 3 | 0 | 0 | 0 |
| `cvpr` | CVPR | 7940 | 785 | 7939 | 819 | 5117 | 0 | 0 | 0 |
| `iclr` | ICLR | 5963 | 5717 | 5963 | 6 | 0 | 5708 | 5708 | 5708 |
| `eccv` | ECCV | 3950 | 816 | 3950 | 3950 | 1 | 0 | 0 | 0 |
| `ijcai` | IJCAI | 2702 | 614 | 2702 | 2702 | 53 | 0 | 0 | 0 |
| `acl_long` | ACL | 2466 | 51 | 2466 | 2466 | 0 | 0 | 0 | 0 |
| `acl_short` | ACL | 173 | 56 | 173 | 173 | 1 | 0 | 0 | 0 |

### 3.3 现状诊断

当前最明显的成果是论文级字段已经完成规模化提速：

- `abstract = 84.9%`
- `doi = 58.7%`

同时也已经显现出结构性缺口：

- `affiliations = 37.7%`
- `author_descriptions / author_experiences / profile_flags = 11.2%`

这说明当前阶段已经不是“机制是否能跑通”的问题，而是“哪些字段受信源结构限制、哪些字段受 API 配额限制”的问题。

## 4. 详细信源与 API 使用情况

### 4.1 OpenReview API

**适用场景**

- 适用于 `detail_url / pdf_url` 中可解析出 `forum_id`（OpenReview 论文 ID）的论文
- 当前主要覆盖 `ICLR`

**可补字段**

- `authors`
- `affiliations`
- `author_descriptions`
- `author_experiences`
- `profile_flags`

**本轮真实用法**

- 先按 `forum_id` 查询 note
- 提取整篇论文的全部 `authorids`
- 对整篇论文的全部作者 profile 逐一查询
- 当前明确采用“全作者查询”，不做前 N 个作者截断

**当前进度**

2026-05-01 的最新进展如下：

- 上一轮 `ICLR / OpenReview` 尾部快照 `3249` 条已跑完
- 结果：新增机构 `2924`，新增作者简介 `2994`，新增作者经历 `2994`，新增 `profile_flags` `2993`
- 当前剩余快照：`data/runtime/iclr_openreview_remaining_enrichment_ids_20260501.txt`
- 当前参数：`--openreview-qps 0.8 --max-profile-requests 0`

当前 `ICLR` 进度如下：

| 指标 | 数量 |
|---|---:|
| 总量 | 5963 |
| 已补机构 | 5717 |
| 已补作者简介 | 5708 |
| 已补作者经历 | 5708 |
| 已补 profile flags | 5708 |
| 仍有机构或任一作者画像字段未补齐 | 255 |

**限制**

| 限制项 | 真实影响 |
|---|---|
| QPS 限制 | 必须控制在 `0.8 req/s` 附近，整体耗时长 |
| 查询粒度 | 需要逐作者 profile 查询，单篇论文成本高 |
| 适用范围 | 只对 OpenReview 体系论文稳定有效 |
| 非 OpenReview 会议 | 无法直接覆盖 `NeurIPS / ECCV / IJCAI / ACL / CVPR` |

### 4.2 arXiv API

**适用场景**

- 已有 `arxiv_id`：按 `id_list` 直接查
- 无 `arxiv_id`：按标题检索尝试命中

**可补字段**

- `arxiv_id`
- `doi`
- `abstract`
- `authors`

**本轮真实效果**

- 对页面中已存在 arXiv 链接的论文有效
- 对纯标题检索命中率有限
- 在 `CVPR` 上配合页面解析效果较好，因为页面本身常含 arXiv 链接

**限制**

| 限制项 | 真实影响 |
|---|---|
| 不提供机构 | 无法补 `affiliations` |
| 不提供作者画像 | 无法补简介、经历、flags |
| 标题检索命中率有限 | 不适合作为全库主路径 |

### 4.3 OpenAlex API

**设计中的角色**

OpenAlex 原本是本轮最关键的通用补全 API，设计上计划覆盖：

- DOI 精确检索
- 标题 + 年份检索
- `abstract`
- `doi`
- `arxiv_id`
- `authors`
- `affiliations`

**理论适用信源**

以下适用范围描述的是能力边界，不代表本轮已实际大规模启用：

- `AAAI`
- `NeurIPS`
- `ECCV`
- `IJCAI`
- `ACL`
- `CVPR`

**当前真实状态**

2026-04-30 执行时，OpenAlex 一度持续返回预算不足；但到 `2026-05-01` 已恢复可用，当前已重新作为非 OpenReview 来源机构补全主路径投入运行。

2026-05-01 已启动的恢复后批次包括：

- `neurips`
- `eccv`
- `ijcai`
- `acl_long`
- `acl_short`（已完成）
- `cvpr`

**限制**

| 限制项 | 真实影响 |
|---|---|
| 预算/速率受限 | 仍需关注日额度与窗口恢复 |
| 结果质量依赖匹配 | 标题检索和年份约束仍需控制误匹配 |
| 覆盖面仍有限 | 即使恢复可用，`NeurIPS / ECCV / IJCAI / ACL / CVPR` 仍有大量机构缺口待跑 |

### 4.4 academic-monitor

设计上保留了 academic-monitor 接口对接能力，但本轮真实探测结果为：

- `http://127.0.0.1:8000/api/v1/identity/enrich-paper`
- 返回：`404 Not Found`

因此本轮真实运行中：

- `--disable-academic-monitor` 被显式启用
- 作者信息由本地 OpenReview profile history 提取逻辑承担

## 5. 各信源与 API 适配关系

### 5.1 信源与 API 适用矩阵

| 信源 | OpenReview | arXiv | OpenAlex | 页面解析兜底 | 真实说明 |
|---|---|---|---|---|---|
| `ICLR` | 强适用 | 弱适用 | 中适用 | 弱适用 | 作者画像优先走 OpenReview |
| `AAAI` | 不适用 | 弱适用 | 强适用 | 强适用 | 页面已补出大量机构，剩余尾差可继续补 |
| `NeurIPS` | 基本不适用 | 弱适用 | 强适用 | 强适用 | 页面已补摘要，机构开始由 OpenAlex 拉升 |
| `ECCV` | 不适用 | 弱适用 | 强适用 | 强适用 | 摘要/DOI 已补，机构正在由 OpenAlex 拉升 |
| `IJCAI` | 不适用 | 弱适用 | 强适用 | 强适用 | 页面可补摘要/DOI，机构正在由 OpenAlex 拉升 |
| `ACL` | 不适用 | 弱适用 | 强适用 | 强适用 | 页面可补摘要/DOI，机构开始由 OpenAlex 拉升 |
| `CVPR` | 不适用 | 中适用 | 强适用 | 强适用 | 页面里常含 arXiv 链接，机构开始由 OpenAlex 拉升 |

### 5.2 字段与 API 适用矩阵

| 字段 | OpenReview | arXiv | OpenAlex | 页面解析兜底 |
|---|---|---|---|---|
| `abstract` | 中 | 强 | 强 | 强 |
| `doi` | 弱 | 中 | 强 | 强 |
| `arxiv_id` | 弱 | 强 | 中 | 中 |
| `authors` | 强 | 中 | 强 | 强 |
| `affiliations` | 强 | 不支持 | 强 | 少数来源支持 |
| `author_descriptions` | 强 | 不支持 | 不支持 | 不支持 |
| `author_experiences` | 强 | 不支持 | 不支持 | 不支持 |
| `profile_flags` | 强 | 不支持 | 不支持 | 不支持 |

### 5.3 页面解析兜底的真实作用

本轮为了保证进度，实际加入了页面解析兜底，当前已接入：

- `CVPR / CVF OpenAccess`
- `ECCV / ECVA`
- `NeurIPS Proceedings`
- `ACL Anthology`
- `IJCAI Proceedings`
- `AAAI OJS`

页面解析兜底的真实作用是：

- 非常适合快速补齐论文级字段
- 对作者画像字段帮助极小
- `AAAI` 是例外，因为其 meta 中直接带 `citation_author_institution`

## 6. 运行限制与长尾问题

### 6.1 API 限额与限速

| 约束类型 | 当前情况 | 影响 |
|---|---|---|
| OpenReview QPS | `0.8 req/s` | 作者画像补全慢，但可持续推进 |
| OpenAlex 配额/预算 | 已恢复，但仍需持续观察 | 非 OpenReview 机构补全已恢复推进，但不能无限并发 |
| academic-monitor | `404 Not Found` | 当前不能作为作者 enrichment 入口 |

### 6.2 页面抓取并发限制

页面型任务本轮主要使用：

- `--concurrency 4~8`
- 默认 `--timeout 25s`
- `AAAI` 长尾场景尝试 `--timeout 8s`

约束原因：

- 并发太低，全库跑不动
- 并发太高，容易触发站点阻断、连接积压和长尾等待

### 6.3 AAAI 长尾问题

在 `AAAI OJS` 尾部批次，出现了较多 TCP 连接长期停留在 `SYN-SENT` 的现象。

真实影响：

- 任务尾部空转明显
- 即使缩短应用层 timeout，也仍受底层建连重试影响
- 因此采用了“中断长尾任务 + 生成剩余快照”的方式止损

### 6.4 已完成的主要执行批次

| 批次 | 状态 | 结果摘要 |
|---|---|---|
| `CVPR` 页面补全 | 已完成 | 更新 7715 行，新增摘要 7204，新增 arXiv ID 5101 |
| `ECCV` 页面补全 | 已完成 | 3950/3950 摘要补齐 |
| `NeurIPS` 页面补全 | 已完成 | 9923/9923 摘要补齐，后续 DOI 已增至 4629 |
| `IJCAI` 页面补全 | 已完成 | 2702/2702 摘要和 DOI 基本补齐 |
| `ACL long/short` 页面补全 | 已完成 | `acl_long` 与 `acl_short` 摘要/DOI 已进一步补齐 |
| `AAAI` 页面补全 | 阶段完成 | 机构 11112/11271，摘要/DOI 10128/11271 |
| `OpenAlex 恢复后机构补缺` | 运行中 | `NeurIPS / ECCV / IJCAI / ACL / CVPR` 正在补机构 |
| `ICLR / OpenReview` | 持续运行中 | 上一轮 3249 条已完成，当前继续收尾剩余 255 条 |

## 7. 后续建议与决策

### 7.1 30 天内

`决策 1（Critical）`

- 持续跑完 `NeurIPS / ECCV / IJCAI / ACL / CVPR` 当前批次，并在完成后回收最新缺口快照
- 目标是优先提升非 OpenReview 来源的机构覆盖率

`决策 2（High）`

- 持续跑完 `ICLR / OpenReview` 当前剩余 `255` 条
- 重点收敛：
  - `author_descriptions`
  - `author_experiences`
  - `profile_flags`
  - `affiliations`

### 7.2 60 天内

`决策 3（Medium）`

- 并行评估新增作者级来源，降低对 OpenReview 的单点依赖
- 优先候选：
  - `Semantic Scholar`
  - `ORCID`
  - `Crossref`
  - `DBLP`

### 7.3 工程改进建议

- 按来源单独配置并发和 timeout
- 对慢站点引入更激进的长尾熔断
- 对剩余未命中行自动生成重试快照
- 将“设计方案”和“真实执行状态”长期拆分记录，避免汇报和执行日志混杂

## 8. 可直接汇报的结论

本轮已经形成一套“多 API + 页面解析兜底”的论文信息补全机制。设计上，主路径包括 `OpenReview API`、`arXiv API` 和 `OpenAlex API`；截至 `2026-05-01`，三条路径都已投入实际补全，`academic-monitor` 仍因 `404` 未启用。结果上，论文级字段补全效果显著，`abstract` 覆盖率已到 `85.1%`，`doi` 覆盖率已到 `60.1%`；机构信息覆盖率已提升到 `37.7%`；作者画像字段目前主要依赖 `OpenReview`，并已在 `ICLR` 上推进到 `5708` 条。当前最主要的瓶颈已经从“机制能否跑通”转向“非 OpenReview 来源机构缺口总量仍大，以及作者画像仍缺少第二信源”。
