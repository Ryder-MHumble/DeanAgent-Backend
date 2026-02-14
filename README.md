# Information Crawler

中关村人工智能研究院**信息监测系统**。自动爬取 85 个信源（63 启用，横跨 9 个维度），通过 v1 REST API（14 端点）供前端查询，同时以 JSON 文件保存至本地。

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
| `scripts/run_batch_crawl.py --dimension <dim>` | 批量测试某维度 |
| `scripts/analyze_selectors.py` | 在目标网页上调试 CSS 选择器 |
| `scripts/investigate_sources.py` | 批量检测信源 URL 可达性 |
| `scripts/seed_sources.py` | YAML → 数据库同步 |
| `scripts/generate_index.py` | 生成 `data/index.json` 索引 |

---

## 维度与信源

### 9 个监测维度

| 维度 ID | 名称 | 源数 | YAML 文件 | 覆盖率 |
|---------|------|------|-----------|--------|
| `national_policy` | 对国家 | 6 | `sources/national_policy.yaml` | ~80% |
| `beijing_policy` | 对北京 | 12 | `sources/beijing_policy.yaml` | ~75% |
| `technology` | 对技术 | 12 | `sources/technology.yaml` | ~90% |
| `talent` | 对人才 | 7 | `sources/talent.yaml` | ~85% |
| `industry` | 对产业 | 8 | `sources/industry.yaml` | ~75% |
| `universities` | 对高校 | 26 | `sources/universities.yaml` | ~90% |
| `events` | 对日程 | 4 | `sources/events.yaml` | ~85% |
| `personnel` | 对人事 | 3 | `sources/personnel.yaml` | ~100% |
| `sentiment` | 对学院舆情 | — | 未创建 | ~30% |
| *(跨维度)* | Twitter 监控 | 7 | `sources/twitter.yaml` | — |

### 爬虫类型分布

```
58 个源 → static（httpx + BS4）
12 个源 → dynamic（Playwright）
 8 个源 → rss（feedparser）
 7 个源 → 自定义 Parser（gov_json_api, twitter_kol, twitter_search, arxiv_api, github_api, hacker_news_api, semantic_scholar）
```

### 配置 → 爬虫路由

YAML 中 `crawler_class`（优先）或 `crawl_method` 决定使用哪个爬虫：

```
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
```

路由逻辑在 `app/crawlers/registry.py`。

---

## 系统架构

### 数据流

```
sources/*.yaml → CrawlerRegistry → 模板/自定义爬虫
                                        ↓
                                  爬取 + 解析
                                        ↓
                                  URL 去重 (SHA-256)
                                        ↓
                        ┌───────────────┴───────────────┐
                        ↓                               ↓
               PostgreSQL (articles)          JSON (data/raw/)
                        ↓
                  REST API (/api/v1)
```

### 项目结构

```
app/
├── main.py                        # FastAPI 入口 + lifespan（启动 scheduler）
├── config.py                      # 配置（DATABASE_URL 等）
├── database.py                    # SQLAlchemy async engine + session
├── models/                        # 4 张 ORM 表
│   ├── article.py                 #   articles（url_hash UNIQUE 去重）
│   ├── source.py                  #   sources（信源注册）
│   ├── crawl_log.py               #   crawl_logs（爬取日志）
│   └── snapshot.py                #   snapshots（快照变更）
├── api/v1/                        # REST API（14 个端点）
│   ├── articles.py                #   /articles CRUD + 搜索 + 统计
│   ├── sources.py                 #   /sources 管理 + 手动触发
│   ├── dimensions.py              #   /dimensions 9 维度概览
│   └── health.py                  #   /health 健康检查
├── crawlers/
│   ├── base.py                    # BaseCrawler + CrawledItem + CrawlResult
│   ├── registry.py                # YAML → 爬虫实例路由
│   ├── templates/                 # 5 种模板爬虫
│   │   ├── static_crawler.py      #   httpx + BS4
│   │   ├── dynamic_crawler.py     #   Playwright + BS4
│   │   ├── rss_crawler.py         #   feedparser
│   │   ├── snapshot_crawler.py    #   hashlib + difflib
│   │   └── social_crawler.py      #   占位
│   ├── parsers/                   # 7 个自定义 API Parser
│   │   ├── gov_json_api.py
│   │   ├── arxiv_api.py
│   │   ├── github_api.py
│   │   ├── hacker_news_api.py
│   │   ├── semantic_scholar.py
│   │   ├── twitter_kol.py
│   │   └── twitter_search.py
│   └── utils/
│       ├── http_client.py         # 共享 httpx（重试、限速、UA 轮换）
│       ├── playwright_pool.py     # Playwright 浏览器单例池
│       ├── dedup.py               # URL 归一化 + SHA-256
│       ├── json_storage.py        # JSON 文件输出
│       └── text_extract.py        # HTML → 文本
├── scheduler/
│   ├── manager.py                 # 读取 YAML → 注册 APScheduler 任务
│   └── jobs.py                    # 单次爬取执行 → 持久化
├── services/                      # 业务逻辑
│   ├── article_service.py         # 文章查询/统计
│   ├── source_service.py          # 信源管理
│   ├── crawl_service.py           # 爬取日志/健康
│   ├── json_reader.py             # 读取 JSON 数据
│   ├── llm_service.py             # LLM 增强（可选）
│   └── twitter_service.py         # Twitter 服务
└── schemas/                       # Pydantic v2 请求/响应
```

---

## API 参考

基础路径 `/api/v1`，启动后访问 `/docs` 查看 Swagger UI。

### 文章 `/articles`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列表（筛选+分页）：`dimension` `source_id` `keyword` `date_from` `date_to` `page` |
| GET | `/search` | 全文搜索（参数同上） |
| GET | `/stats` | 聚合统计：`group_by=dimension\|source\|day` |
| GET | `/{id}` | 详情 |
| PATCH | `/{id}` | 更新：`is_read` `importance` |

### 信源 `/sources`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列表（可按 `dimension` 过滤） |
| GET | `/{source_id}` | 详情 |
| GET | `/{source_id}/logs` | 爬取日志 |
| PATCH | `/{source_id}` | 启用/禁用 |
| POST | `/{source_id}/trigger` | 手动触发爬取 |

### 维度 `/dimensions`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 9 维度概览（文章数 + 最后更新） |
| GET | `/{dimension}` | 维度下文章列表 |

### 健康 `/health`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 系统状态（DB + Scheduler） |
| GET | `/crawl-status` | 爬取健康（healthy/warning/failing 统计） |

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

**JSON 文件**：`data/raw/{dimension}/{group}/{source_id}/{YYYY-MM-DD}.json`
```
data/raw/
├── national_policy/policy/gov_cn_zhengce/2026-02-13.json
├── technology/academic/arxiv_cs_ai/2026-02-13.json
└── universities/ai_institutes/tsinghua_air/2026-02-13.json
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

**已完成**：项目骨架 · 4 ORM 表 · 5 模板爬虫 + 7 自定义 Parser · v1 API 14 端点 · 85 信源配置（63 启用）· APScheduler 调度 · JSON 输出（56 个数据文件）· LLM/Twitter 服务

**已删除**：v2 业务 API 层（13 端点 + schemas + business services）— 需重新规划

**待完成**：业务 API 重建 · 详情页内容抓取 · sentiment 维度 · ~10 失效 URL · RSSHub 替代 · Alembic 迁移 · 测试 · 部署验证

**设计文档**：`docs/信源爬取方案/`（9 份按维度）· `docs/TODO.md`（任务优先级）
