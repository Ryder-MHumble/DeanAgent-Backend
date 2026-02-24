# Information Crawler

中关村人工智能研究院**信息监测系统**。自动爬取 134 个信源（109 启用，横跨 9 个维度），通过 v1 REST API（22 端点，含 intel 业务智能 8 端点）供前端查询，同时以 JSON 文件保存至本地。
82 个启用信源已配置 `detail_selectors` 或 RSS/API 自带正文，可自动获取文章正文。

**技术栈**：FastAPI · SQLAlchemy (async) · PostgreSQL (Supabase) · APScheduler 3.x · httpx · BeautifulSoup4 · Playwright · feedparser

---

## 快速开始

```bash
# 安装
pip install -e ".[dev]"
playwright install chromium

# 配置（必填 DATABASE_URL）
cp .env.example .env

# 启动（自动同步信源 + 注册调度）
uvicorn app.main:app --reload
# API 文档 → http://localhost:8000/docs
```

环境要求：Python 3.11+ · PostgreSQL · Node.js（Playwright 需要）

完整环境变量见 [.env.example](.env.example)，必填项只有 `DATABASE_URL`。

---

## 问题定位指南

遇到问题时，按下表快速找到对应文件：

### 爬虫问题

| 现象 | 去哪里看 | 怎么测 |
|------|----------|--------|
| **某个信源**抓不到/选择器失效 | `sources/{维度}.yaml` → 该源的 `selectors` / `url` | `python scripts/run_single_crawl.py --source <id>` |
| **static 类型**整体不工作 | `app/crawlers/templates/static_crawler.py` | 同上，选一个 static 源测试 |
| **dynamic 类型**超时/白屏 | `app/crawlers/templates/dynamic_crawler.py` + YAML 中 `wait_for`/`wait_timeout` | 同上，选一个 dynamic 源测试 |
| **rss 类型**解析异常 | `app/crawlers/templates/rss_crawler.py` | 同上 |
| **snapshot 类型**没检测到变化 | `app/crawlers/templates/snapshot_crawler.py` | 同上 |
| **自定义 Parser** 出错（arxiv/github/twitter…） | `app/crawlers/parsers/{name}.py` | 同上 |
| 不知道源用哪个爬虫 | `app/crawlers/registry.py` 的路由映射 | — |

### 基础设施问题

| 现象 | 去哪里看 |
|------|----------|
| HTTP 请求失败 / 被封 / 限速 | `app/crawlers/utils/http_client.py`（重试、UA 轮换、限速） |
| Playwright 浏览器池异常 | `app/crawlers/utils/playwright_pool.py` |
| 文章重复入库 / 去重失效 | `app/crawlers/utils/dedup.py` + `app/models/article.py`（url_hash UNIQUE） |
| JSON 文件没输出 | `app/crawlers/utils/json_storage.py` |
| 调度不执行 / 频率不对 | `app/scheduler/manager.py` + YAML 中 `schedule`/`is_enabled` |
| API 返回异常 | `app/api/v1/{articles,sources,dimensions,health}.py` |
| 数据库连接失败 | `app/config.py`（DATABASE_URL） + `app/database.py` |

### 调试脚本

| 脚本 | 用途 |
|------|------|
| `scripts/run_single_crawl.py --source <id>` | 隔离测试单个信源 |
| `scripts/run_all_crawl.py` | 批量运行所有启用信源 |
| `scripts/seed_sources.py` | YAML → 数据库同步 |
| `scripts/generate_index.py` | 生成 `data/index.json` 索引 |
| `scripts/migrate_json_to_latest.py` | 日期文件迁移为 `latest.json` 格式 |

---

## 维度与信源

### 9 个监测维度

| 维度 ID | 名称 | 源数 | 启用 | YAML 文件 |
|---------|------|------|------|-----------|
| `national_policy` | 国家政策 | 8 | 6 | `sources/national_policy.yaml` |
| `beijing_policy` | 北京政策 | 14 | 10 | `sources/beijing_policy.yaml` |
| `technology` | 技术动态 | 34 | 33 | `sources/technology.yaml` |
| `talent` | 人才发展 | 7 | 4 | `sources/talent.yaml` |
| `industry` | 产业趋势 | 10 | 6 | `sources/industry.yaml` |
| `universities` | 高校动态 | 55 | 46 | `sources/universities.yaml` |
| `events` | 活动日程 | 6 | 4 | `sources/events.yaml` |
| `personnel` | 人事变动 | 4 | 4 | `sources/personnel.yaml` |
| twitter | 社交舆情 | 7 | 7 | `sources/twitter.yaml`† |

> † `sources/twitter.yaml` 的 7 个源按 `dimension` 字段跨维度分配：technology 4 源、industry 1 源、talent 1 源、sentiment 1 源。需配置 Twitter API key。

### 爬虫类型分布

```mermaid
pie title 信源爬虫类型分布
    "static (httpx + BS4)" : 85
    "dynamic (Playwright)" : 22
    "rss (feedparser)" : 10
    "自定义 Parser (API)" : 17
```

### 配置 → 爬虫路由

YAML 中 `crawler_class`（优先）或 `crawl_method` 决定使用哪个爬虫：

```text
crawl_method: static   → app/crawlers/templates/static_crawler.py
crawl_method: dynamic  → app/crawlers/templates/dynamic_crawler.py
crawl_method: rss      → app/crawlers/templates/rss_crawler.py
crawl_method: snapshot → app/crawlers/templates/snapshot_crawler.py

crawler_class: gov_json_api      → app/crawlers/parsers/gov_json_api.py
crawler_class: arxiv_api         → app/crawlers/parsers/arxiv_api.py
crawler_class: github_api        → app/crawlers/parsers/github_api.py
crawler_class: hacker_news_api   → app/crawlers/parsers/hacker_news_api.py
crawler_class: semantic_scholar  → app/crawlers/parsers/semantic_scholar.py
crawler_class: twitter_kol       → app/crawlers/parsers/twitter_kol.py
crawler_class: twitter_search    → app/crawlers/parsers/twitter_search.py
crawler_class: hunyuan_api       → app/crawlers/parsers/hunyuan_api.py
```

路由逻辑在 `app/crawlers/registry.py`，详见 [架构文档](docs/architecture.md)。

---

## 系统架构

### 核心架构

```mermaid
graph TD
    YAML["sources/*.yaml<br/>9 维度 YAML 配置"] --> Scheduler["APScheduler<br/>定时调度"]
    Scheduler --> Registry["CrawlerRegistry<br/>双轨路由"]

    Registry -->|"crawler_class<br/>(优先)"| Custom["自定义 Parser ×8<br/>gov_json · arxiv · github<br/>hacker_news · semantic_scholar<br/>twitter_kol · twitter_search · hunyuan"]
    Registry -->|"crawl_method<br/>(兜底)"| Template["模板爬虫 ×4"]

    subgraph Templates["模板爬虫"]
        direction LR
        Static["static<br/>httpx + BS4"]
        Dynamic["dynamic<br/>Playwright + BS4"]
        RSS["rss<br/>feedparser"]
        Snapshot["snapshot<br/>hash + diff"]
    end

    Template --> Templates

    Custom --> Base["BaseCrawler<br/>去重 · 计时 · 异常处理"]
    Templates --> Base

    Base --> DB["PostgreSQL (Supabase)<br/>articles · sources<br/>crawl_logs · snapshots"]
    Base --> JSON["本地 JSON<br/>data/raw/{dim}/{group}/{id}/"]

    DB --> CoreAPI["核心 API ×14<br/>/articles · /sources<br/>/dimensions · /health"]
    DB --> IntelAPI["业务智能 API ×8<br/>/intel/policy · /intel/personnel"]

    style YAML fill:#e1f5fe
    style Registry fill:#e8eaf6
    style Base fill:#e8f5e9
    style DB fill:#fff3e0
    style CoreAPI fill:#fce4ec
    style IntelAPI fill:#f3e5f5
```

### 数据流（文本版）

```
sources/*.yaml → APScheduler → CrawlerRegistry → 模板/自定义爬虫
                                                       ↓
                                                 爬取 + 解析
                                                       ↓
                                                 URL 去重 (SHA-256)
                                                       ↓
                                   ┌───────────────────┴──────────────────┐
                                   ↓                                      ↓
                          PostgreSQL (articles)                 JSON (data/raw/)
                                   ↓
                     ┌─────────────┴──────────────┐
                     ↓                            ↓
              核心 API (/api/v1)         业务智能 (/api/v1/intel)
```

### 项目结构

```text
app/
├── main.py                        # FastAPI 入口 + lifespan（启动 scheduler）
├── config.py                      # 配置（DATABASE_URL 等）
├── database.py                    # SQLAlchemy async engine + session
├── models/                        # 4 张 ORM 表
│   ├── article.py                 #   articles（url_hash UNIQUE 去重）
│   ├── source.py                  #   sources（信源注册）
│   ├── crawl_log.py               #   crawl_logs（爬取日志）
│   └── snapshot.py                #   snapshots（快照变更）
├── api/v1/                        # REST API（22 个端点）
│   ├── articles.py                #   /articles CRUD + 搜索 + 统计
│   ├── sources.py                 #   /sources 管理 + 手动触发
│   ├── dimensions.py              #   /dimensions 9 维度概览
│   ├── health.py                  #   /health 健康检查
│   └── intel/                     #   业务智能子路由
│       ├── router.py              #     聚合注册
│       ├── policy.py              #     政策智能（feed/opportunities/stats）
│       └── personnel.py           #     人事情报（feed/changes/stats/enriched）
├── crawlers/
│   ├── base.py                    # BaseCrawler + CrawledItem + CrawlResult
│   ├── registry.py                # YAML → 爬虫实例路由（双轨：模板 + 自定义）
│   ├── templates/                 # 4 种模板爬虫
│   │   ├── static_crawler.py      #   httpx + BS4
│   │   ├── dynamic_crawler.py     #   Playwright + BS4
│   │   ├── rss_crawler.py         #   feedparser
│   │   └── snapshot_crawler.py    #   hashlib + difflib
│   ├── parsers/                   # 8 个自定义 API Parser
│   │   ├── gov_json_api.py        #   国务院 JSON 搜索
│   │   ├── arxiv_api.py           #   ArXiv Atom
│   │   ├── github_api.py          #   GitHub REST
│   │   ├── hacker_news_api.py     #   HN Firebase
│   │   ├── semantic_scholar.py    #   学术搜索
│   │   ├── twitter_kol.py         #   Twitter KOL
│   │   ├── twitter_search.py      #   Twitter 搜索
│   │   └── hunyuan_api.py         #   腾讯混元
│   └── utils/                     # 共享工具
│       ├── selector_parser.py     #   列表/详情页解析引擎（static/dynamic 共享）
│       ├── http_client.py         #   httpx（重试、限速、UA 轮换）
│       ├── playwright_pool.py     #   Playwright 浏览器池
│       ├── dedup.py               #   URL 归一化 + SHA-256
│       ├── json_storage.py        #   JSON 文件输出（latest.json）
│       ├── html_sanitizer.py      #   HTML 清洗
│       └── image_extractor.py     #   图片提取
├── scheduler/
│   ├── manager.py                 # 读取 YAML → 注册 APScheduler 任务
│   └── jobs.py                    # 单次爬取执行 → 持久化
├── services/                      # 核心业务逻辑
│   ├── article_service.py
│   ├── source_service.py
│   ├── crawl_service.py
│   ├── dimension_service.py
│   └── intel/                     # 业务智能模块
│       ├── shared.py              #   共享工具（keyword_score 等）
│       ├── policy/                #   政策智能（rules + llm + service）
│       └── personnel/             #   人事情报（rules + llm + service）
└── schemas/                       # Pydantic v2 请求/响应
    └── intel/                     # 业务智能 schemas

sources/                           # YAML 配置（每维度一个文件）
scripts/                           # 运维脚本
data/raw/                          # 本地 JSON 输出
data/processed/                    # 业务智能处理输出
```

---

## API 参考

基础路径 `/api/v1`，启动后访问 `/docs` 查看 Swagger UI。共 22 个端点。

### 核心端点（14 个）

**文章 `/articles`**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列表（筛选+分页）：`dimension` `source_id` `keyword` `date_from` `date_to` `page` |
| GET | `/search` | 全文搜索（参数同上） |
| GET | `/stats` | 聚合统计：`group_by=dimension\|source\|day` |
| GET | `/{id}` | 详情 |
| PATCH | `/{id}` | 更新：`is_read` `importance` |

**信源 `/sources`**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列表（可按 `dimension` 过滤） |
| GET | `/{source_id}` | 详情 |
| GET | `/{source_id}/logs` | 爬取日志 |
| PATCH | `/{source_id}` | 启用/禁用 |
| POST | `/{source_id}/trigger` | 手动触发爬取 |

**维度 `/dimensions`**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 9 维度概览（文章数 + 最后更新） |
| GET | `/{dimension}` | 维度下文章列表 |

**健康 `/health`**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 系统状态（DB + Scheduler） |
| GET | `/crawl-status` | 爬取健康（healthy/warning/failing 统计） |

### 业务智能端点（8 个）`/intel`

**政策智能 `/intel/policy`**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/feed` | 政策动态 Feed（规则引擎 + LLM 富化，含匹配度评分、资金信息） |
| GET | `/opportunities` | 政策机会（筛选可申报的资助/项目） |
| GET | `/stats` | 政策统计（按分类、重要性、时间聚合） |

**人事情报 `/intel/personnel`**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/feed` | 人事动态 Feed（文章级，含自动提取的任免变动） |
| GET | `/changes` | 人事变动列表（人员级，正则提取姓名/职务/机构） |
| GET | `/stats` | 人事统计 |
| GET | `/enriched-feed` | LLM 富化 Feed（含 relevance/group/actionSuggestion） |
| GET | `/enriched-stats` | 富化统计 |

---

## 信源配置

### 标准信源（零代码）

编辑 `sources/{dimension}.yaml` 添加条目：

```yaml
- id: "gov_cn_zhengce"              # 唯一 ID
  name: "中国政府网-最新政策"         # 显示名称
  group: "policy"                    # 分组（决定 JSON 输出子目录）
  url: "https://www.gov.cn/zhengce/"
  crawl_method: "static"             # static / dynamic / rss / snapshot
  schedule: "2h"                     # 2h / 4h / daily / weekly / monthly
  priority: 1
  is_enabled: true
  selectors:
    list_item: "ul.list li"          # 列表容器
    title: "a"                       # 标题
    link: "a"                        # 链接
    date: "span.date"               # 日期
    date_format: "%Y-%m-%d"
  base_url: "https://www.gov.cn"    # 补全相对链接
  tags: ["policy"]
  keyword_filter: ["人工智能"]       # 可选关键词过滤
```

dynamic 类型额外需要：
```yaml
  wait_for: "div.list li"           # Playwright 等待选择器
  wait_timeout: 15000               # 超时（ms）
```

### 自定义 Parser

1. `app/crawlers/parsers/` 新建类（继承 `BaseCrawler`）
2. `app/crawlers/registry.py` → `_CUSTOM_MAP` 注册
3. YAML 中 `crawler_class: "your_parser_name"`

---

## 数据输出

**数据库**：4 张表 — `articles`（url_hash 去重）· `sources` · `crawl_logs` · `snapshots`

**原始 JSON**：`data/raw/{dimension}/{group}/{source_id}/latest.json`（覆盖模式，每条标记 `is_new`）

```text
data/raw/
├── national_policy/policy/gov_cn_zhengce/latest.json
├── technology/academic/arxiv_cs_ai/latest.json
└── universities/ai_institutes/tsinghua_air/latest.json
```

**业务智能输出**：`data/processed/` 下按模块分目录

```text
data/processed/
├── policy_intel/          # 政策智能
│   ├── feed.json          #   政策动态（规则引擎 + LLM 评分）
│   └── opportunities.json #   政策机会（可申报项目）
└── personnel_intel/       # 人事情报
    ├── feed.json          #   人事动态
    ├── changes.json       #   任免变动（正则提取）
    └── enriched_feed.json #   LLM 富化版
```

---

## 部署

```bash
# Docker
docker build -t information-crawler .
docker run -p 8000:8000 --env-file .env information-crawler

# Render（render.yaml 已配置）
# 健康检查：/api/v1/health
# 免费计划建议：MAX_CONCURRENT_CRAWLS=3, PLAYWRIGHT_MAX_CONTEXTS=2
```

---

## 项目状态

**已完成**：

- 4 ORM 表 + 4 种模板爬虫 + 8 个自定义 Parser
- 134 信源配置（109 启用），82 源可获取正文
- v1 API 22 端点（含 intel 业务智能 8 端点）
- APScheduler 定时调度 + JSON 本地输出
- 业务智能：政策智能（规则引擎 + LLM 二级管线）+ 人事情报（正则提取 + LLM 富化）
- 代码 Review：static/dynamic 共享 selector_parser，消除 ~100 行重复

**待完成**：sentiment 维度扩展 · 部分禁用高校源修复 · Alembic 迁移 · 测试覆盖 · 部署验证

详见 `docs/TODO.md`。

---

## 项目文档

| 文档 | 路径 | 内容 |
|------|------|------|
| 架构设计 | `docs/architecture.md` | 爬虫框架核心架构、数据流、Mermaid 图 |
| 爬取状态 | `docs/CrawlStatus.md` | 各维度各源的爬取状态、数据量 |
| 任务优先级 | `docs/TODO.md` | P0-P3 分级待办 |
| 部署指南 | `docs/deployment.md` | 服务器需求、资源控制 |
| 院长需求 | `docs/院长智能体.md` | 前端 Dean-Agent 功能需求 |
