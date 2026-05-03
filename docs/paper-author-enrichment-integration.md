# Papers 作者信息补充 · 接入指南

> 2026-04-30

## 已完成

### academic-monitor 侧（权威实现）

分支：`feat/openreview-identity-component` · 两个 commit：
- `9fab94d` 初版 OpenReview 身份核验组件
- `1d536cb` 加 profile_extractor + /enrich-paper API

能力：
- `POST /api/identity/enrich-author` — 单作者查询
- `POST /api/identity/enrich-paper` — 整篇论文批量查询，按 author_order 对齐

返回字段（每个作者）：
- `author_description` — 由 OpenReview history 生成的中文摘要
- `author_experiences` — 结构化学校经历列表
- `institutions` / `current_affiliation` — 机构列表与当前机构
- `links` / `preferred_email` — 外部链接与邮箱
- `profile_flags` — `is_chinese` / `is_current_student` + evidence
- `resolution` — 说明 profile_id 是直接给的还是 forum 反查出来的

### DeanAgent 侧

分支：`feat/paper-author-enrichment-via-academic-monitor` · 1 个 commit：
- `fe9f092`
  - `scripts/sql/20260430_add_paper_author_enrichment_fields.sql` — papers 表加 3 个 JSONB 字段
  - `app/services/scholar/profile_classifier.py` — 注释标注 academic-monitor 为权威词典源

**未做的事（需要你决定何时接入）**：
- `scripts/crawl/enrich_paper_metadata.py` 的调用接入

## 为什么 enrich_paper_metadata.py 没接入

这个文件在你本地是 untracked（git 没追踪过）状态，说明是进行中的工作。我不应该把正在进行的代码和我自己的 feature 混在一起 commit，否则你未来想回滚任何一方都会波及对方。

## 推荐接入时机

等 `scripts/crawl/enrich_paper_metadata.py` 先被你 commit 到 main（或任意稳定分支）之后，再基于稳定状态加我的改动。

## 具体接入步骤（你 commit 了 enrich_paper_metadata.py 之后）

在 `scripts/crawl/enrich_paper_metadata.py` 做如下 4 处扩展：

### 1. 顶部加 academic-monitor 配置

```python
import os

ACADEMIC_MONITOR_BASE_URL = os.environ.get(
    "ACADEMIC_MONITOR_API_URL", "http://127.0.0.1:8000"
).rstrip("/")
ACADEMIC_MONITOR_ENRICH_PAPER_PATH = "/api/identity/enrich-paper"
ACADEMIC_MONITOR_TIMEOUT = float(os.environ.get("ACADEMIC_MONITOR_TIMEOUT", "60"))
```

### 2. `EnrichmentResult` 加 3 个字段

```python
@dataclass(slots=True)
class EnrichmentResult:
    ...（已有字段）
    author_descriptions: list[dict[str, Any]] = field(default_factory=list)
    author_experiences: list[dict[str, Any]] = field(default_factory=list)
    profile_flags: list[dict[str, Any]] = field(default_factory=list)

    def as_update(self) -> dict[str, Any]:
        return {
            ...（已有键）
            "author_descriptions": self.author_descriptions,
            "author_experiences": self.author_experiences,
            "profile_flags": self.profile_flags,
        }
```

### 3. 新增函数 `fetch_author_enrichment_from_academic_monitor`

调 academic-monitor `/api/identity/enrich-paper`：传 authors + 可选的 authorids（从 fetch_openreview 的 note 中拿）+ 现有 affiliations，返回三个字段。失败静默返回 None。

完整实现详见本次 PR 的 academic-monitor commit `1d536cb`。

### 4. 在 `enrich_row` gather 之后调用它

```python
results = await asyncio.gather(*tasks)
combined = combine_results(results)
...

if ids.openreview_id and combined.authors:
    author_enrichment = await fetch_author_enrichment_from_academic_monitor(
        client,
        paper_id=row.get("paper_id"),
        forum_id=ids.openreview_id,
        authors=combined.authors,
        authorids=[],  # 让 academic-monitor 自己走 forum_lookup
        existing_affiliations=combined.affiliations,
    )
    if author_enrichment is not None:
        combined = combine_results([combined, author_enrichment])
```

### 5. SQL 扩展

- `select_candidate_rows`：SELECT 加上 `author_descriptions, author_experiences, profile_flags`，WHERE 加 `OR profile_flags IS NULL OR profile_flags = '[]'::jsonb`
- `update_row`：UPDATE SET 加三个新字段

## 环境变量

生产部署时在 `.env` 加：

```bash
ACADEMIC_MONITOR_API_URL=http://academic-monitor-host:8000
ACADEMIC_MONITOR_TIMEOUT=60
```

## 端到端验证

1. 应用 SQL migration：`psql -f scripts/sql/20260430_add_paper_author_enrichment_fields.sql`
2. 启动 academic-monitor：`uvicorn src.api.main:app --port 8000`（在 academic-monitor 目录）
3. 测试一次单行：`python scripts/crawl/enrich_paper_metadata.py --paper-id xxx --limit 1`
4. 查 papers 表：`SELECT author_descriptions, author_experiences, profile_flags FROM papers WHERE paper_id = 'xxx';`

## 降级行为

- academic-monitor 不可达 → 三个新字段保持 `'[]'::jsonb`，其他字段照常更新
- OpenReview API 429 → academic-monitor 内部已有指数退避 + 磁盘缓存，透传给上游
- profile 查不到 → 返回空字段，不报错
