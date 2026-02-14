# Information Crawler - Project Context

## Overview

中关村人工智能研究院信息监测系统。自动爬取 ~100 个信源（横跨 8 个维度），通过 REST API 供前端查询，同时将爬取数据以 JSON 文件保存至本地。

**技术栈**: FastAPI + SQLAlchemy(async) + PostgreSQL(Supabase) + APScheduler 3.x + httpx + BeautifulSoup4 + Playwright + feedparser

## 8 个维度

| ID | 中文名 | 预估源数 |
|---|---|---|
| national_policy | 对国家 | ~21 |
| beijing_policy | 对北京 | ~14 |
| technology | 对技术 | ~23 |
| talent | 对人才 | ~10 |
| industry | 对产业 | ~13 |
| sentiment | 对学院舆情 | ~6 |
| universities | 对高校 | ~35 |
| events | 对日程 | ~4 |

## 项目结构

```
Information_Crawler/
├── app/
│   ├── main.py                    # FastAPI 入口 + lifespan（启动 scheduler、关闭 Playwright）
│   ├── config.py                  # Pydantic Settings（DATABASE_URL, RSSHUB_BASE_URL 等）
│   ├── database.py                # SQLAlchemy async engine + session factory
│   ├── models/                    # ORM 模型
│   │   ├── base.py                # DeclarativeBase
│   │   ├── article.py             # articles 表（url_hash UNIQUE 去重）
│   │   ├── source.py              # sources 表（信源注册）
│   │   ├── crawl_log.py           # crawl_logs 表（爬取执行日志）
│   │   └── snapshot.py            # snapshots 表（快照差异历史）
│   ├── schemas/                   # Pydantic v2 请求/响应 schema
│   ├── api/v1/                    # REST API 路由（19 个端点）
│   │   ├── articles.py            # /api/v1/articles (CRUD + 搜索 + 统计)
│   │   ├── sources.py             # /api/v1/sources (列表 + 手动触发)
│   │   ├── dimensions.py          # /api/v1/dimensions (8 维度概览)
│   │   └── health.py              # /api/v1/health (健康 + 爬取状态)
│   ├── crawlers/
│   │   ├── base.py                # BaseCrawler(ABC) + CrawledItem + CrawlResult + CrawlStatus
│   │   ├── registry.py            # CrawlerRegistry: YAML config -> 爬虫实例
│   │   ├── templates/             # 5 种模板爬虫
│   │   │   ├── rss_crawler.py     # RSSCrawler (feedparser + httpx)
│   │   │   ├── static_crawler.py  # StaticHTMLCrawler (httpx + BS4)
│   │   │   ├── snapshot_crawler.py # SnapshotDiffCrawler (hashlib + difflib)
│   │   │   ├── dynamic_crawler.py # DynamicPageCrawler (Playwright + BS4)
│   │   │   └── social_crawler.py  # SocialMediaCrawler (placeholder)
│   │   ├── parsers/               # 自定义 API Parser（尚未实现）
│   │   │   └── __init__.py
│   │   └── utils/
│   │       ├── http_client.py     # 共享 httpx 客户端（重试、限速、UA 轮换）
│   │       ├── playwright_pool.py # Playwright 浏览器单例池
│   │       ├── dedup.py           # URL 归一化 + SHA-256 哈希（保留 fragment）
│   │       └── text_extract.py    # HTML 转文本、摘要截断
│   ├── scheduler/
│   │   ├── manager.py             # SchedulerManager: 读取 YAML、注册 APScheduler 任务、auto-seed DB
│   │   └── jobs.py                # execute_crawl_job: 实例化爬虫 -> 持久化 Article + CrawlLog
│   └── services/                  # 业务逻辑层（article_service, source_service, crawl_service）
├── sources/                       # YAML 信源配置（按维度分文件）
│   ├── national_policy.yaml       # ✅ 已创建（6 源）
│   └── technology.yaml            # ✅ 已创建（11 源）
├── data/
│   ├── raw/                       # 原始爬取数据（按 维度/分组/源/日期 组织）
│   └── refined/                   # 业务数据（LLM 处理后，按日期/维度/场景 组织）
├── scripts/
│   ├── run_single_crawl.py        # CLI 单源测试
│   └── seed_sources.py            # YAML -> sources 表同步
├── alembic/                       # 数据库迁移（未生成 initial migration）
├── tests/                         # 测试（空目录结构已创建）
├── 信源爬取方案/                    # 9 份设计文档 + 实施任务计划
├── pyproject.toml                 # Python 3.11+, 依赖列表
├── Dockerfile
└── render.yaml
```

## 架构核心

### 配置驱动爬虫

YAML 中的 `crawl_method` → 模板爬虫类；`crawler_class` → 自定义 Parser（优先级更高）。
`CrawlerRegistry.create_crawler(config)` 完成路由。

```yaml
# 标准信源：零代码，只需 YAML 配置 + CSS 选择器
- id: "ndrc_policy"
  crawl_method: "static"
  selectors: { list_item: "ul.u-list li", title: "a", link: "a", date: "span" }

# API 信源：YAML 指定 crawler_class，parsers/ 下编写 Parser
- id: "hacker_news"
  crawler_class: "hacker_news_api"
```

### 去重策略

1. **URL 级**: `normalize_url()` 去 utm_* 参数 + lowercase → SHA-256 → `url_hash UNIQUE` 约束
2. **内容级**: `compute_content_hash()` 折叠空白 → SHA-256 → `content_hash` 软检查

### 调度

- APScheduler 3.x `AsyncIOScheduler`（NOT 4.x alpha）
- 频率: `2h`/`4h`/`daily`/`weekly`/`monthly` → IntervalTrigger / CronTrigger
- 防雷群: 随机 jitter 0~300s
- `max_instances=1` 防止单源重叠

### 数据输出

- **数据库**: PostgreSQL (Supabase) — articles 表，通过 REST API 查询
- **JSON 文件**: `data/raw/{dimension}/{group}/{source_id}/{YYYY-MM-DD}.json` — 本地持久化备份（group 为 YAML 中的分组字段）

## 当前状态

### 已完成

- [x] 项目骨架（pyproject.toml, FastAPI app, config, database）
- [x] 4 张 ORM 表（articles, sources, crawl_logs, snapshots）
- [x] 5 种模板爬虫（rss, static, snapshot, dynamic, social placeholder）
- [x] CrawlerRegistry + 共享工具（http_client, dedup, text_extract, playwright_pool）
- [x] 19 个 REST API 端点
- [x] APScheduler 调度管理器 + 任务执行器
- [x] 2/8 YAML 配置（national_policy 6 源, technology 11 源）
- [x] CLI 测试脚本（run_single_crawl.py, seed_sources.py）
- [x] 代码审查 + 5 个关键 bug 修复
- [x] ~126 个数据源可达性测试（HTTP accessibility check）

### 未完成

- [ ] 6 个 YAML 配置：beijing_policy, talent, industry, sentiment, universities, events
- [ ] 5 个自定义 Parser: gov_json_api, arxiv_api, hacker_news_api, github_api, semantic_scholar
- [x] JSON 本地文件输出功能（已实现，按 dimension/group/source_id/date.json 结构输出）
- [ ] ~10 个失效 URL 更新（NSFC path 变更, gov.cn 部分路径 404 等）
- [ ] RSSHub 替代方案（公共实例全部 403，需自部署或切换原生 feed）
- [ ] Alembic initial migration
- [ ] 单元测试 / 集成测试
- [ ] 部署验证

## 关键设计决策

1. **APScheduler 3.x (NOT 4.x)**: 4.x 是 alpha，pip 安装不到稳定版
2. **URL 归一化保留 fragment**: snapshot_crawler 用 `#snapshot-{hash}` 区分同 URL 的不同快照
3. **scheduler 启动时 auto-seed sources 到 DB**: 避免 FK violation
4. **CrawlLog 记录 crawler 创建失败**: 即使爬虫实例化出错也可通过 API 追溯
5. **RSSHub 公共实例不可用**: rsshub.app / rsshub.rssforever.com / rsshub.moeyy.cn 全部限流/403。解决方案：(1) 自部署 RSSHub (2) 使用原生 RSS feed（机器之心 /rss, Google AI Blog 等都有原生 feed）

## 可达性摘要

| 维度 | 可行性 | 备注 |
|---|---|---|
| technology | ~90% | RSS/API 覆盖好；RSSHub 源需替换为原生 feed |
| universities | ~90% | 高校官网大多正常 |
| events | ~85% | aideadlines YAML, wikicfp 正常 |
| talent | ~85% | people.cn/xinhuanet 正常 |
| national_policy | ~80% | gov.cn 正常；NSFC/NPC 需路径修正 |
| beijing_policy | ~75% | 部分 URL 已变更 |
| industry | ~75% | 36kr/虎嗅/TMT 正常；交易所部分 403 |
| sentiment | ~30% | 社交媒体需 Cookie 或逆向，难度最高 |

## 开发约定

- **Python 3.11+**, 使用 `X | Y` 联合类型语法
- **ruff** 格式化 + lint (line-length=100)
- **pytest + pytest-asyncio** (asyncio_mode="auto")
- **async everywhere**: 所有 DB 操作、HTTP 请求、爬虫都是 async
- 爬虫新增信源：标准源只需 YAML；API 源在 `parsers/` 加一个类 + registry 注册
- 环境变量通过 `.env` + `pydantic-settings` 管理
- 不使用 `git add .`，按文件名显式暂存

## 运行命令

```bash
# 安装依赖
pip install -e ".[dev]"

# 启动服务
uvicorn app.main:app --reload

# 测试单源爬取
python scripts/run_single_crawl.py --source ndrc_policy

# 运行测试
pytest

# Lint
ruff check app/
```

## 设计文档

详见 `信源爬取方案/` 目录下 9 份文档（00-08），以及 `09_实施任务计划.md` 中的后续实施步骤。
