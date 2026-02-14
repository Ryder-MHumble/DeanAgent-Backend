# 实施任务计划

> 本文档记录所有待完成的开发任务，供后续对话中的模型参考和执行。
> 每个任务标注了优先级、依赖关系和验证方式。

---

## Phase 2A: JSON 本地输出 + 核心管道可运行

**目标**: 让爬虫管道脱离数据库也能工作，爬取结果保存为本地 JSON 文件。

### Task 2A-1: JSON 文件输出模块

- **文件**: `app/crawlers/utils/json_storage.py`（新建）
- **功能**:
  - `save_crawl_result_json(result: CrawlResult, source_config: dict)` 函数
  - 输出路径: `data/{dimension}/{source_id}/{YYYY-MM-DD}.json`
  - 每次爬取追加到当天文件（同一天多次爬取合并，按 url_hash 去重）
  - JSON 格式: `{ "source_id": "...", "dimension": "...", "crawled_at": "...", "items": [...] }`
  - 每个 item 包含: title, url, published_at, author, summary, content, tags, extra
- **验证**: `python scripts/run_single_crawl.py --source ndrc_policy` 后检查 `data/national_policy/ndrc_policy/` 目录

### Task 2A-2: 集成 JSON 输出到爬取管道

- **文件**: `app/scheduler/jobs.py` 修改
- **改动**: 在 `execute_crawl_job()` 中，持久化 Article 之后（或之前），调用 `save_crawl_result_json()`
- **注意**: JSON 输出应独立于数据库操作，即使 DB 不可用也能保存 JSON
- **验证**: 启动 scheduler 让一个源跑一次，确认 JSON 文件生成

### Task 2A-3: 无数据库模式支持

- **文件**: `app/crawlers/base.py` 修改, `scripts/run_single_crawl.py` 修改
- **改动**:
  - `BaseCrawler.run()` 增加 `db_session=None` 参数，当 DB 不可用时跳过去重直接返回所有 items
  - `run_single_crawl.py` 增加 `--no-db` 标志，仅输出到 JSON 文件
- **验证**: `python scripts/run_single_crawl.py --source ndrc_policy --no-db`

---

## Phase 2B: 补全 YAML 配置（6 个维度）

**目标**: 补全所有 9 个维度的 YAML 信源配置。

### Task 2B-1: beijing_policy.yaml

- **文件**: `sources/beijing_policy.yaml`（新建）
- **参考**: `信源爬取方案/02_对北京.md`
- **预计源数**: ~14
- **关键源**:
  - 北京市政府 (首都之窗) https://www.beijing.gov.cn — static
  - 中关村管委会 — static（注意 zgc.gov.cn SSL 不稳定，用 HTTP）
  - 海淀区政府 — static（/zwgk/ 路径已失效，需用首页）
  - 北京经信局 — static
  - 北京科委 — static（/col/col2954/ 已失效，需找新路径）
- **注意**: 部分 URL 已失效，需要先验证再配置。失效源设 `is_enabled: false`

### Task 2B-2: talent.yaml

- **文件**: `sources/talent.yaml`（新建）
- **参考**: `信源爬取方案/04_对人才.md`
- **预计源数**: ~10
- **关键源**:
  - 人民网-人事频道 http://renshi.people.com.cn — static
  - 新华网-人事频道 — static
  - 国家公务员局 — static
  - CSRankings — 自定义 parser (CSV)
  - AI Conference Deadlines — 自定义 parser (YAML)
  - IEEE Fellows / ACM Awards — static

### Task 2B-3: industry.yaml

- **文件**: `sources/industry.yaml`（新建）
- **参考**: `信源爬取方案/05_对产业.md`
- **预计源数**: ~13
- **关键源**:
  - 36氪快讯 — rss
  - 虎嗅 — static
  - 钛媒体 — static
  - 界面新闻 — static
  - 澎湃 — static
  - 亿欧 — static
  - SEC EDGAR — 自定义 parser (API)
  - 上交所/深交所 — static（上交所 403，需特殊处理）

### Task 2B-4: sentiment.yaml

- **文件**: `sources/sentiment.yaml`（新建）
- **参考**: `信源爬取方案/06_对学院_舆情.md`
- **预计源数**: ~6
- **关键源**:
  - 微博搜索 — social (需 Cookie)
  - 知乎 — social (需 Cookie)
  - 哔哩哔哩 — social (API 可用)
  - 小红书 — social (最难，需逆向)
- **可行性**: ~30%，社交媒体最难。建议先实现 B站 API（无需 Cookie），其余设 `is_enabled: false`
- **注意**: Cookie 通过环境变量注入（WEIBO_COOKIE, XIAOHONGSHU_COOKIE）

### Task 2B-5: universities.yaml

- **文件**: `sources/universities.yaml`（新建）
- **参考**: `信源爬取方案/07_对高校.md`
- **预计源数**: ~35（数量最多的维度）
- **关键源**:
  - C9 高校 AI 学院官网（清华、北大、复旦、上交、浙大、中科大、南大、哈工大、西交）— static
  - 中科院系统（自动化所、计算所）— static
  - 国家级 AI 研究院（BAAI、之江、鹏城、上海 AI Lab）— static
  - QS/THE/ARWU 排名 — static（ShanghaiRanking 可访问）
  - Nature Index — static
- **注意**: 南大新闻 SSL 失败 → 设 is_enabled: false 或用 HTTP

### Task 2B-7: personnel.yaml ✅ 已完成 (2026-02-14)

- **文件**: `sources/personnel.yaml`（新建）
- **源数**: 3
- **信源**:
  - `mohrss_rsrm`: 人社部-国务院人事任免（dynamic + Playwright + detail_selectors 详情页正文抓取）
  - `moe_renshi`: 教育部-人事任免（static，从 universities.yaml 迁移）
  - `moe_renshi_si`: 教育部-人事司公告（static，从 universities.yaml 迁移）
- **验证**: 3/3 全部通过，mohrss_rsrm 含详情页正文提取（任免人名+职位+单位）

### Task 2B-6: events.yaml

- **文件**: `sources/events.yaml`（新建）
- **参考**: `信源爬取方案/08_对日程.md`
- **预计源数**: ~4
- **关键源**:
  - AI Conference Deadlines (aideadlin.es) — 自定义 parser（YAML/JSON 格式）
  - WikiCFP — static
  - 活动行/互动吧 — static
  - HuggingFace daily papers — 自定义 parser (API)

---

## Phase 2C: 自定义 API Parser

**目标**: 实现 5 个已在 `registry.py` 注册但尚未编写的自定义 Parser。

### Task 2C-1: gov_json_api.py（国务院政策文件库 JSON API）

- **文件**: `app/crawlers/parsers/gov_json_api.py`（新建）
- **API**: `http://sousuo.gov.cn/s.htm?t=govall&q=人工智能&timetype=timeqb&sort=pubtime`
- **或**: `https://www.gov.cn/zhengce/zhengceku/` 页面 JSON 接口
- **验证**: 已测试可用，返回结构化 JSON（title, url, pubtimeStr, source）
- **注意**: 中文搜索词需 URL 编码

### Task 2C-2: arxiv_api.py（ArXiv REST API）

- **文件**: `app/crawlers/parsers/arxiv_api.py`（新建）
- **API**: `http://export.arxiv.org/api/query?search_query=cat:cs.AI&sortBy=submittedDate&max_results=20`
- **格式**: Atom XML
- **字段**: title, summary, author(s), published, links
- **验证**: 已测试可用

### Task 2C-3: hacker_news_api.py（Hacker News Firebase API）

- **文件**: `app/crawlers/parsers/hacker_news_api.py`（新建）
- **API**:
  - Top stories: `https://hacker-news.firebaseio.com/v0/topstories.json`
  - Item detail: `https://hacker-news.firebaseio.com/v0/item/{id}.json`
- **逻辑**: 取 top 30 stories → 并发获取每个 item 详情 → 过滤 AI 相关
- **验证**: 已测试可用

### Task 2C-4: github_api.py（GitHub REST/Trending）

- **文件**: `app/crawlers/parsers/github_api.py`（新建）
- **API**: `https://api.github.com/search/repositories?q=AI+language:python&sort=stars&order=desc`
- **或**: 爬 https://github.com/trending 页面
- **字段**: full_name, description, stargazers_count, html_url, topics
- **注意**: GitHub API 无认证限制 60 req/h，有 token 则 5000/h

### Task 2C-5: semantic_scholar.py（Semantic Scholar API）

- **文件**: `app/crawlers/parsers/semantic_scholar.py`（新建）
- **API**: `https://api.semanticscholar.org/graph/v1/paper/search?query=artificial+intelligence&limit=20&fields=title,abstract,authors,year,url`
- **格式**: JSON
- **验证**: 已测试可用

---

## Phase 2D: 失效 URL 修复

**目标**: 根据可达性测试结果，更新 YAML 中的失效 URL。

### Task 2D-1: national_policy.yaml URL 修复

- `nsfc_news`: `/publish/portal0/tab434/` → 需改为 `https://www.nsfc.gov.cn/csc/20345/20348/index.html` 或类似有效路径
- `gov_cn_zhengce`: RSSHub 依赖 → 需切换为直接爬取 gov.cn 列表页或使用 gov_json_api parser

### Task 2D-2: technology.yaml URL 修复

- `theverge_ai_rss`: `/rss/ai-artificial-intelligence/index.xml` 404 → 改为 `/rss/index.xml`（主 RSS，用 keyword_filter 过滤 AI）
- `jiqizhixin_rss`: RSSHub 不可用 → 改用原生 `https://www.jiqizhixin.com/rss`
- `36kr_ai_rss`: RSSHub 不可用 → 改用 36kr 原生 API 或 static 爬取
- `reddit_*_rss`: RSSHub 不可用 → Reddit 原生 RSS: `https://www.reddit.com/r/MachineLearning/.rss`

### Task 2D-3: 全局 RSSHub 策略调整

- **问题**: rsshub.app 及所有已知公共实例返回 403/503
- **方案 A**: 将所有 RSSHub 源改为原生 RSS feed（优先）
- **方案 B**: 自部署 RSSHub Docker 实例（备选）
- **需要修改**: `app/config.py` 中 RSSHUB_BASE_URL 的默认值可能需要移除
- **影响范围**: national_policy.yaml (gov_cn_zhengce), technology.yaml (jiqizhixin, 36kr, reddit)

---

## Phase 3: 测试 + 数据库迁移

### Task 3-1: Alembic initial migration

- **文件**: `alembic/versions/` 下生成初始迁移
- **命令**: `alembic revision --autogenerate -m "initial tables"`
- **前提**: 需要可连接的 PostgreSQL 实例或 Supabase

### Task 3-2: 单元测试 - 爬虫模块

- **文件**: `tests/unit/test_crawlers/`
- **覆盖**:
  - `test_dedup.py`: normalize_url, compute_url_hash, compute_content_hash
  - `test_registry.py`: CrawlerRegistry 路由逻辑
  - `test_rss_crawler.py`: mock feedparser 输入
  - `test_static_crawler.py`: mock HTML 输入
  - `test_json_storage.py`: JSON 文件写入/合并

### Task 3-3: 集成测试 - 端到端爬取

- **文件**: `tests/integration/`
- **覆盖**:
  - 选 1-2 个实际可用源（如 ArXiv API, TechCrunch RSS）做真实爬取
  - 验证 JSON 文件生成
  - 验证去重（连续爬两次，第二次 items_new=0）

---

## Phase 4: 稳定运行 + 部署

### Task 4-1: 错误恢复与重试机制

- **文件**: `app/crawlers/utils/http_client.py` 改进
- **功能**: 指数退避重试、超时处理、连接池管理

### Task 4-2: 日志与监控增强

- **功能**: 结构化日志、每日爬取汇总、失败源告警阈值

### Task 4-3: Docker 本地运行验证

- **命令**: `docker build -t info-crawler . && docker run -p 8000:8000 info-crawler`
- **验证**: 健康端点 + 手动触发爬取 + JSON 输出

### Task 4-4: Render 部署

- **文件**: `render.yaml` + `Dockerfile`
- **环境变量**: DATABASE_URL, SUPABASE_URL, SUPABASE_KEY

---

## 执行顺序建议

```
2A-1 → 2A-2 → 2A-3     (JSON 输出，让系统可脱离 DB 运行)
    ↓
2B-1 ~ 2B-6             (补全 YAML 配置，可并行)
    ↓
2C-1 ~ 2C-5             (自定义 Parser，可并行)
    ↓
2D-1 ~ 2D-3             (URL 修复，需逐一验证)
    ↓
3-1 → 3-2 → 3-3         (测试 + 迁移)
    ↓
4-1 → 4-2 → 4-3 → 4-4  (稳定化 + 部署)
```

**最小可交付物**: 完成 Phase 2A + 2B + 2C 后，系统即可分维度爬取并输出 JSON，可作为阶段性交付。
