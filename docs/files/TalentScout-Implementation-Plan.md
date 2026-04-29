# 人才猎头引擎 — Codex 实现方案

> 为 DeanAgent-Backend 新增 `talent_scout` 维度，从竞赛/论文/GitHub 三个渠道采集 AI 人才数据。
> **不是从零开始** — 已有 `github_api`、`semantic_scholar` parser 和 `scholars` 表可复用。

---

## 一、整体架构

```
数据采集层（新增 Custom Parsers）
├── kaggle_leaderboard    → Kaggle Grandmasters/Masters 名单
├── openreview_authors    → 顶会论文作者（ICML/ICLR/NeurIPS/AAAI）
├── acl_anthology_authors → ACL/EMNLP 论文作者
├── dblp_disambiguation   → DBLP 作者消歧 Hub
├── competition_winners   → 竞赛获奖名单（CCF BDCI/ICPC/RoboMaster 等）
└── [已有] github_api    → 复用现有，扩展为"AI repo 主要贡献者"

数据存储层（复用 + 新增）
├── [已有] scholars 表    → 存储人才主记录
├── [新增] talent_profiles 表 → 竞赛/论文/GitHub 多维度画像
└── [新增] talent_identities 表 → 身份消歧关联表

API 层（新增端点）
└── /api/v1/talent-scout/* → 查询/搜索/导出
```

---

## 二、数据源详细分析（含真实 URL）

### 渠道 1：竞赛获奖者

| 竞赛 | 真实 URL | API/数据格式 | Parser 类型 | 难度 |
|------|---------|-------------|------------|------|
| **Kaggle** | `https://www.kaggle.com/rankings.json?group=competitions&segment=COMBINED&page=1` | JSON API，无需认证即可获取 leaderboard | `kaggle_leaderboard` | ⭐ |
| **天池** | `https://tianchi.aliyun.com/competition/` + `https://tianchi.aliyun.com/api/v1/competitions?page=1&pageSize=20` | 需登录态，JSON API | 静态爬虫 + 动态 | ⭐⭐ |
| **CCF BDCI** | `https://www.datafountain.cn/competitions` | 网页列表，非结构化 | 静态爬虫 | ⭐⭐ |
| **ICPC** | `https://icpc.global/ranklist` + `https://icpc.global/api/contest-ranklist/` | JSON API（需探测） | `competition_winners` | ⭐⭐ |
| **RoboMaster** | `https://www.robomaster.com/zh-CN/resource/pages/announcement/1024` | 官网公示 | 静态爬虫 | ⭐⭐ |
| **KDD Cup** | `https://kdd.org/kdd-cup` + 相关 leaderboard | 年度变化 | 静态/手动 | ⭐⭐⭐ |
| **NeurIPS Comp** | `https://nips.cc/Conferences/2025/CompetitionTrack` | 顶会页面 | 静态爬虫 | ⭐⭐ |
| **华为软件精英** | `https://developer.huawei.com/consumer/cn/software/elite/` | 官网公示 | 静态爬虫 | ⭐⭐ |

### 渠道 2：顶会高质量论文作者

| 数据源 | 真实 URL | 数据格式 | 说明 |
|--------|---------|---------|------|
| **OpenReview API v2** | `https://api2.openreview.net/notes?content.venue=ICML+2025&limit=100` | JSON API，无需认证 | 覆盖 ICML、ICLR、NeurIPS、AAAI |
| | `https://api2.openreview.net/notes?id=<paper_id>` | 详情含作者+机构 | |
| **ACL Anthology** | `https://aclanthology.org/` (API: `https://aclanthology.org/api/`) | REST API + JSON | ACL、EMNLP、NAACL |
| | `https://aclanthology.org/venues/acl/` | 按 venue 筛选 | |
| **Semantic Scholar** | `https://api.semanticscholar.org/graph/v1/paper/search?query=...&fields=authors,citationCount` | JSON API，有 rate limit | **已有 parser**，需扩展为作者维度 |
| **DBLP API** | `https://dblp.org/search/publ/api?q=author:Ming+Li&format=json&h=30` | JSON API，无需认证 | **消歧核心 Hub** |
| | `https://dblp.org/pid/00/1234.xml` | 作者详情页（XML） | 每个作者有唯一 pid |
| **CVF Open Access** | `https://openaccess.thecvf.com/CVPR2025` | 网页，有年度 index | CVPR、ICCV |
| **Google Scholar** | 无官方 API，需 SerpAPI 等第三方 | — | 不推荐作为主源 |

### 渠道 3：GitHub 主要贡献者

| 数据源 | 真实 URL | 说明 |
|--------|---------|------|
| **GitHub Search API** | `https://api.github.com/search/repositories?q=topic:machine-learning+language:python&sort=stars&order=desc` | **已有 `github_api` parser** |
| **GitHub Contributors API** | `https://api.github.com/repos/{owner}/{repo}/contributors?per_page=30` | 需要扩展现有 parser |
| **GitHub User API** | `https://api.github.com/users/{username}` | 获取邮箱、公司、博客 |

### 身份消歧 Hub：DBLP

| 接口 | URL | 说明 |
|------|-----|------|
| 作者搜索 | `https://dblp.org/search/publ/api?q=author:Wei+Zhang&format=json` | 返回该姓名的所有作者 pid |
| 作者详情 | `https://dblp.org/pid/00/1234.xml` | 返回所有论文列表，可用于确认身份 |
| Co-author 网络 | 从详情页解析 | 可用于交叉验证 |

---

## 三、新增文件清单

### 3.1 新增 Custom Parsers（`app/crawlers/parsers/`）

```
app/crawlers/parsers/
├── kaggle_leaderboard.py      [新增] Kaggle 排行榜爬虫
├── openreview_authors.py      [新增] OpenReview 顶会论文作者
├── acl_anthology_authors.py   [新增] ACL Anthology 论文作者
├── competition_winners.py     [新增] 多赛事获奖名单聚合
└── github_contributors.py     [新增] 扩展 GitHub 为贡献者维度
```

### 3.2 新增 YAML 配置（`sources/`）

```
sources/
└── talent/talent_scout.yaml   [新增] 人才猎头信源配置
```

### 3.3 新增/修改文件

```
app/crawlers/registry.py       [修改] 注册 5 个新 parser
app/db/
├── talent_dao.py              [新增] 人才数据访问层
app/api/v1/
├── talent_scout.py            [新增] 人才猎头 API 端点
app/schemas/
├── talent_scout.py            [新增] Pydantic schemas
scripts/
├── migrate_talent_scout.py    [新增] 数据库迁移脚本
```

---

## 四、Parser 实现细节

### 4.1 `kaggle_leaderboard.py`

```python
"""Kaggle 排行榜爬虫 — 采集 Grandmaster/Master 名单"""
# 目标 URL:
#   排行榜: https://www.kaggle.com/rankings.json?group=competitions&segment=COMBINED&page=1
#   用户详情: https://www.kaggle.com/{username}
#
# 返回 CrawledItem:
#   - title: 用户名
#   - url: Kaggle 个人主页
#   - author: 用户名
#   - extra: {tier, total_gold, total_silver, total_bronze, rank}
#
# 注意: Kaggle 公开 JSON API 无需认证，但有 rate limit
# 每页 20 条，需要翻页采集（max_pages 配置，默认 5 页 = 100 人）
```

**关键实现点：**
- 使用 `fetch_json` 调用 Kaggle rankings API
- 翻页逻辑：`page=1,2,3,...`
- 过滤 tier=grandmaster/master
- 通过 GitHub API 交叉查找同名用户获取邮箱（可选）

### 4.2 `openreview_authors.py`

```python
"""OpenReview 顶会论文作者爬虫 — 从 ICML/ICLR/NeurIPS/AAAI 采作者"""
# 目标 URL:
#   论文搜索: https://api2.openreview.net/notes?content.venue=ICML+2025&limit=100
#   论文详情: https://api2.openreview.net/notes?id=<paper_id>
#
# 配置项:
#   - venues: ['ICML 2025', 'ICLR 2025', 'NeurIPS 2025']
#   - max_papers_per_venue: 200
#   - min_citations: 0  (可选过滤)
#
# 返回 CrawledItem (每个作者一条):
#   - title: "{作者名} — {论文数} papers at {venue}"
#   - url: OpenReview profile URL
#   - author: 作者名
#   - extra: {venues: [...], paper_count, affiliations: [...], orcid}
#
# 消歧策略:
#   OpenReview 每个作者有 profile URL (https://openreview.net/profile?id=xxx)
#   同一个 profile 下的论文天然已消歧
#   但跨 venue 需要按 profile URL 去重
```

**关键实现点：**
- OpenReview v2 API 无需认证
- `content.venue` 筛选会议
- `content.authors` 返回作者列表，每个有 `id`（profile URL）
- 按 `author.id` 聚合，统计每个作者在所有目标会议的论文数

### 4.3 `acl_anthology_authors.py`

```python
"""ACL Anthology 论文作者爬虫 — ACL/EMNLP/NAACL"""
# 目标 URL:
#   Anthology API: https://aclanthology.org/api/
#   XML 数据: https://aclanthology.org/anthology+acl.bib (BibTeX 导出)
#   网页: https://aclanthology.org/events/acl-2025/
#
# 注意: ACL Anthology 是开源项目 (github.com/acl-org/acl-anthology)
#       数据可批量下载: https://aclanthology.org/anthology+abstracts.bib.gz
#
# 推荐方案: 下载 XML/BibTeX 批量解析，而非逐页爬
#   - XML dump: https://aclanthology.org/anthology.xml
#   - 解析后按作者聚合
#
# 返回格式同 openreview_authors
```

### 4.4 `competition_winners.py`

```python
"""多赛事获奖名单聚合爬虫 — CCF BDCI/ICPC/RoboMaster 等"""
# 这是一个聚合型 parser，内部按赛事分派到不同子爬虫
#
# 目标 URLs:
#   CCF BDCI:  https://www.datafountain.cn/competitions  (需分赛事解析)
#   ICPC:      https://icpc.global/api/contest-ranklist/{year}/{region}
#   RoboMaster: https://www.robomaster.com/zh-CN/resource/pages/announcement/1024
#   华为精英:  https://developer.huawei.com/consumer/cn/software/elite/
#   NeurIPS Comp: https://nips.cc/Conferences/2025/CompetitionTrack
#
# 返回 CrawledItem (每条 = 一个获奖团队/个人):
#   - title: "{竞赛名} {奖项} — {团队/个人名}"
#   - url: 获奖页面链接
#   - extra: {competition, award, members: [{name, university}], year}
#
# 实现建议: 先做 Kaggle (最容易验证)，再逐步添加其他赛事
```

### 4.5 `github_contributors.py`

```python
"""GitHub 主要贡献者爬虫 — AI repo 贡献者"""
# 扩展现有 github_api.py 的能力
#
# 目标 URLs:
#   仓库搜索: https://api.github.com/search/repositories?q=topic:llm&sort=stars&order=desc
#   贡献者:   https://api.github.com/repos/{owner}/{repo}/contributors?per_page=30
#   用户详情: https://api.github.com/users/{username}
#
# 流程:
#   1. 搜索高 star AI 仓库 (复用现有逻辑)
#   2. 对每个 top repo，拉取 top contributors
#   3. 对每个 contributor，获取用户详情 (email, company, blog)
#   4. 按 contributor 聚合，统计跨 repo 贡献
#
# 返回 CrawledItem (每个贡献者一条):
#   - title: "{login} — {contributions} contributions to {N} AI repos"
#   - url: GitHub profile URL
#   - author: login
#   - extra: {repos: [...], total_contributions, email, company, blog}
#
# Rate Limit 注意:
#   GitHub API 未认证 60 req/hr，认证 5000 req/hr
#   需要 .env 中配 GITHUB_TOKEN
```

---

## 五、数据库设计

### 5.1 `talent_profiles` 表（新增）

```sql
CREATE TABLE talent_profiles (
    id TEXT PRIMARY KEY,             -- 生成规则: "{source}:{identifier}"
    name TEXT NOT NULL,              -- 姓名
    source TEXT NOT NULL,            -- 来源: kaggle/openreview/acl/github/competition
    source_url TEXT,                 -- 原始链接
    affiliations TEXT[],             -- 所属机构列表
    email TEXT,                      -- 邮箱（如果能获取到）
    
    -- 竞赛维度
    competitions JSONB DEFAULT '[]', -- [{name, award, year, team}]
    
    -- 论文维度
    papers JSONB DEFAULT '[]',       -- [{title, venue, year, citations, url}]
    paper_count INT DEFAULT 0,
    total_citations INT DEFAULT 0,
    
    -- GitHub 维度
    github_login TEXT,
    github_contributions JSONB DEFAULT '{}', -- {repos: [...], total_contributions}
    
    -- 消歧
    dblp_pid TEXT,                   -- DBLP 作者 ID（消歧后填入）
    orcid TEXT,                      -- ORCID
    scholar_id TEXT,                 -- 关联 scholars 表
    
    -- 元数据
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    confidence_score FLOAT DEFAULT 0.0,  -- 消歧置信度
    tags TEXT[] DEFAULT '{}'
);

CREATE INDEX idx_talent_profiles_name ON talent_profiles (name);
CREATE INDEX idx_talent_profiles_source ON talent_profiles (source);
CREATE INDEX idx_talent_profiles_dblp ON talent_profiles (dblp_pid) WHERE dblp_pid IS NOT NULL;
CREATE INDEX idx_talent_profiles_affiliations ON talent_profiles USING GIN (affiliations);
```

### 5.2 与现有 `scholars` 表的关系

```
talent_profiles (新人才数据)
    ↓ scholar_id 关联
scholars (已有学者数据，2686 条)

关系: 1:1 或 N:1（同一人可能有多个 profile 来自不同源）
消歧后通过 scholar_id 打通
```

---

## 六、注册与配置

### 6.1 `registry.py` 修改

在 `_CUSTOM_MAP` 中新增 5 个条目：

```python
_CUSTOM_MAP: dict[str, str] = {
    # ... 现有条目 ...
    "kaggle_leaderboard": "app.crawlers.parsers.kaggle_leaderboard.KaggleLeaderboardCrawler",
    "openreview_authors": "app.crawlers.parsers.openreview_authors.OpenReviewAuthorsCrawler",
    "acl_anthology_authors": "app.crawlers.parsers.acl_anthology_authors.ACLAnthologyAuthorsCrawler",
    "competition_winners": "app.crawlers.parsers.competition_winners.CompetitionWinnersCrawler",
    "github_contributors": "app.crawlers.parsers.github_contributors.GitHubContributorsCrawler",
}
```

### 6.2 `sources/talent/talent_scout.yaml`

```yaml
dimension: "talent_scout"
dimension_name: "AI人才猎头"
description: "从竞赛/论文/GitHub三个渠道采集AI人才数据"

default_keyword_filter: []  # 人才数据不需要关键词过滤

sources:
  # === 渠道1: 竞赛获奖者 ===
  - id: "kaggle_grandmasters"
    name: "Kaggle Grandmasters"
    group: "competition"
    url: "https://www.kaggle.com/rankings.json"
    crawl_method: "static"
    crawler_class: "kaggle_leaderboard"
    schedule: "monthly"
    priority: 2
    is_enabled: true
    tier_filter: ["grandmaster", "master"]
    max_pages: 5
    tags: ["competition", "kaggle", "ml"]

  # === 渠道2: 顶会论文作者 ===
  - id: "openreview_icml"
    name: "OpenReview-ICML"
    group: "conference"
    url: "https://api2.openreview.net/notes"
    crawl_method: "static"
    crawler_class: "openreview_authors"
    schedule: "monthly"
    priority: 1
    is_enabled: true
    venues: ["ICML 2025", "ICML 2024"]
    max_papers_per_venue: 200
    tags: ["conference", "icml", "papers"]

  - id: "openreview_iclr"
    name: "OpenReview-ICLR"
    group: "conference"
    url: "https://api2.openreview.net/notes"
    crawl_method: "static"
    crawler_class: "openreview_authors"
    schedule: "monthly"
    priority: 1
    is_enabled: true
    venues: ["ICLR 2025", "ICLR 2024"]
    max_papers_per_venue: 200
    tags: ["conference", "iclr", "papers"]

  - id: "openreview_neurips"
    name: "OpenReview-NeurIPS"
    group: "conference"
    url: "https://api2.openreview.net/notes"
    crawl_method: "static"
    crawler_class: "openreview_authors"
    schedule: "monthly"
    priority: 1
    is_enabled: true
    venues: ["NeurIPS 2025", "NeurIPS 2024"]
    max_papers_per_venue: 200
    tags: ["conference", "neurips", "papers"]

  - id: "acl_anthology"
    name: "ACL Anthology"
    group: "conference"
    url: "https://aclanthology.org/"
    crawl_method: "static"
    crawler_class: "acl_anthology_authors"
    schedule: "monthly"
    priority: 1
    is_enabled: true
    venues: ["acl-2025", "acl-2024", "emnlp-2024"]
    tags: ["conference", "acl", "emnlp", "papers"]

  # === 渠道3: GitHub 贡献者 ===
  - id: "github_ai_contributors"
    name: "GitHub AI贡献者"
    group: "github"
    url: "https://api.github.com/search/repositories"
    crawl_method: "static"
    crawler_class: "github_contributors"
    schedule: "monthly"
    priority: 2
    is_enabled: true
    search_topics: ["llm", "large-language-model", "machine-learning", "deep-learning", "agent"]
    min_stars: 500
    max_repos: 30
    top_contributors_per_repo: 10
    github_token_env: "GITHUB_TOKEN"
    tags: ["github", "opensource", "developer"]
```

---

## 七、实现步骤（Codex 执行顺序）

### Step 1: 数据库迁移
**文件**: `scripts/migrate_talent_scout.py`
- 创建 `talent_profiles` 表
- 添加索引
- 验证迁移

### Step 2: Base Parser 实现（最简单的先做）
**2a**: `app/crawlers/parsers/kaggle_leaderboard.py`
- 调用 `https://www.kaggle.com/rankings.json?group=competitions&segment=COMBINED&page=1`
- 返回 CrawledItem 列表
- 先只做 Kaggle，验证整个 pipeline

**2b**: `app/crawlers/parsers/openreview_authors.py`
- 调用 `https://api2.openreview.net/notes?content.venue=ICML+2025&limit=100`
- 解析作者，按 profile URL 聚合

### Step 3: GitHub 扩展
**文件**: `app/crawlers/parsers/github_contributors.py`
- 基于现有 `github_api.py` 扩展
- 搜索高 star 仓库 → 拉贡献者 → 获取用户详情

### Step 4: ACL Anthology
**文件**: `app/crawlers/parsers/acl_anthology_authors.py`
- 下载 XML dump 或调用 API
- 解析作者信息

### Step 5: 竞赛聚合
**文件**: `app/crawlers/parsers/competition_winners.py`
- 先实现 ICPC (最结构化)
- 再逐个添加其他赛事

### Step 6: YAML 配置 & 注册
- 创建 `sources/talent/talent_scout.yaml`
- 修改 `app/crawlers/registry.py` 注册新 parsers

### Step 7: API 端点
- `app/api/v1/talent_scout.py`
- 基本端点：`GET /api/v1/talent-scout/profiles` (分页查询)
- 筛选：按来源、机构、竞赛、论文数、citations
- 导出：CSV/JSON

### Step 8: 身份消歧（后续迭代）
- DBLP pid 对齐
- 跨源合并（同一人在多个源出现）
- 与 scholars 表关联

---

## 八、验证方式

每个 Parser 实现后，用以下命令单独测试：

```bash
# 测试单个 parser
python scripts/run_single_crawl.py --source kaggle_grandmasters
python scripts/run_single_crawl.py --source openreview_icml
python scripts/run_single_crawl.py --source github_ai_contributors

# 验证数据库写入
python scripts/verify_db_migration.py talent_profiles --check-fields name,source,affiliations

# 测试 API 端点
curl http://10.1.132.21:8001/api/v1/talent-scout/profiles?source=kaggle&limit=10
```

---

## 九、优先级排序（建议）

| 优先级 | 任务 | 原因 |
|--------|------|------|
| P0 | Kaggle Leaderboard Parser | 数据最结构化，无需认证，最快出结果 |
| P0 | OpenReview Authors Parser | 论文渠道核心，API 公开，数据质量高 |
| P1 | GitHub Contributors Parser | 已有基础代码，扩展成本低 |
| P1 | talent_profiles 表 + 基础 API | 数据落地 + 可查询 |
| P2 | ACL Anthology Parser | 数据量大，需批量下载 |
| P2 | Competition Winners Parser | 多赛事适配工作量大 |
| P3 | 身份消歧 | 需要前三个渠道数据积累后才能做 |

---

## 十、⚠️ 注意事项

1. **Rate Limit**: 
   - Kaggle: 无明确限制，但翻页不宜太快
   - OpenReview: 官方建议 < 1 req/s
   - GitHub: 未认证 60/hr，认证 5000/hr（**必须配 GITHUB_TOKEN**）
   - ACL Anthology: 开源数据，建议批量下载而非逐页爬

2. **数据量预估**:
   - Kaggle Grandmasters: ~200 人
   - OpenReview (ICML+ICLR+NeurIPS+AAAI): ~5000-10000 个唯一作者
   - ACL Anthology: ~10000+ 个唯一作者
   - GitHub AI top repos: ~30 repos × 10 contributors = ~300 人
   - 竞赛: ~500-1000 人/年

3. **身份消歧是后续迭代**，不要在第一版追求完美消歧。先采集、存储，再逐步对齐。

4. **.env 需要新增**:
   ```
   GITHUB_TOKEN=ghp_xxxx  # GitHub API 认证（已有 github_api parser 则可能已配）
   ```
