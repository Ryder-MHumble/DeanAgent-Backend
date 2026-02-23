# Information Crawler — AI 开发上下文

中关村人工智能研究院信息监测系统。134 信源（109 启用）× 9 维度，5 种模板爬虫 + 8 个自定义 Parser，v1 API 22 端点（含 intel 业务智能 8 端点）。
82 个启用信源已配置 detail_selectors 或 RSS/API 自带正文，可自动获取文章正文（content 字段）。
技术栈：FastAPI + SQLAlchemy(async) + PostgreSQL(Supabase) + APScheduler 3.x + httpx + BS4 + Playwright。

## ⚠ 每次修改后必须做的事

**代码改完 → 验证通过 → 更新文档。三步缺一不可。**

### 必须更新的文档

每次修改爬虫代码、YAML 配置、或整体功能后，**必须同步更新以下文档**：

| 改了什么 | 必须更新 | 更新什么 |
|---------|---------|---------|
| 某个信源的 YAML（选择器/URL/启用状态） | `docs/CrawlStatus.md` | 该信源所在维度的状态表（条目数、启用状态、说明） |
| 新增/删除信源 | `docs/CrawlStatus.md` + `docs/TODO.md` | 总览表的源数统计、分组表、对应维度详情；TODO 中对应条目标记完成 |
| 新增维度 | `docs/CrawlStatus.md` + `docs/TODO.md` + `app/services/dimension_service.py` | 总览表新增行、新建维度详情章节、DIMENSION_NAMES 新增 |
| 爬虫模板改动 | `docs/CrawlStatus.md` | 如影响信源状态则更新对应维度表 |
| 修复禁用源 | `docs/CrawlStatus.md` + `docs/TODO.md` | 禁用源表删除该行、状态表更新为启用、TODO 对应条目打勾 |
| API 端点增删 | `docs/TODO.md` | 更新 API 相关待办状态 |
| 任何功能完成 | `docs/TODO.md` | 对应条目标记 `[x]` 完成 |

### 文档更新格式

`docs/CrawlStatus.md` 顶部有「最后更新」行，每次修改都要更新日期：
```markdown
> 最后更新: 2026-XX-XX
```

`docs/TODO.md` 顶部同理：
```markdown
> 最后更新: 2026-XX-XX
```

---

## 问题定位索引

**某个信源爬不到数据 / 选择器失效：**
→ `sources/{dimension}.yaml` 找到该源的 `selectors` / `url` 配置
→ `python scripts/run_single_crawl.py --source <id>` 单独测试
→ 用 Playwright MCP `browser_snapshot` 分析真实 DOM 结构

**某种爬虫类型（static/dynamic/rss/snapshot）整体出问题：**
→ `app/crawlers/templates/{type}_crawler.py`
→ `app/crawlers/utils/selector_parser.py`（static/dynamic 共享的列表解析、日期提取、详情页解析）

**自定义 Parser（arxiv/github/twitter 等）出问题：**
→ `app/crawlers/parsers/{name}.py`
→ 路由映射在 `app/crawlers/registry.py` 的 `_CUSTOM_MAP`

**Playwright 页面加载失败 / 超时：**
→ `app/crawlers/templates/dynamic_crawler.py`（爬虫逻辑）
→ `app/crawlers/utils/playwright_pool.py`（浏览器池）
→ YAML 中检查 `wait_for` / `wait_timeout`

**文章重复入库 / 去重不对：**
→ `app/crawlers/utils/dedup.py`（normalize_url + hash 逻辑）
→ `app/models/article.py`（url_hash UNIQUE 约束）

**调度任务不执行 / 频率不对：**
→ `app/scheduler/manager.py`（任务注册 + 频率映射）
→ `app/scheduler/jobs.py`（单次执行逻辑）
→ YAML 中检查 `schedule` / `is_enabled`

**API 返回异常：**
→ `app/api/v1/{articles,sources,dimensions,health}.py`（核心端点）
→ `app/api/v1/intel/{policy,personnel}.py`（业务智能端点）
→ `app/services/{article,source,crawl,dimension}_service.py`（核心业务逻辑）
→ `app/services/intel/{policy,personnel}/service.py`（业务智能逻辑）
→ `app/schemas/`（请求/响应校验）

**JSON 文件没输出 / 路径不对：**
→ `app/crawlers/utils/json_storage.py`
→ 输出路径：`data/raw/{dimension}/{group}/{source_id}/latest.json`

**HTTP 请求失败 / 限速 / UA 被封：**
→ `app/crawlers/utils/http_client.py`（重试、限速、UA 轮换）

**数据库连接 / 表结构问题：**
→ `app/database.py`（engine + session）
→ `app/models/{article,source,crawl_log,snapshot}.py`（4 张表）
→ `app/config.py`（DATABASE_URL 配置）

## 文件路由规则

**配置驱动**：YAML `crawl_method` → 模板爬虫；`crawler_class` → 自定义 Parser（优先级更高）
```
crawl_method: static  → app/crawlers/templates/static_crawler.py
crawl_method: dynamic → app/crawlers/templates/dynamic_crawler.py
crawl_method: rss     → app/crawlers/templates/rss_crawler.py
crawl_method: snapshot→ app/crawlers/templates/snapshot_crawler.py
crawler_class: gov_json_api      → app/crawlers/parsers/gov_json_api.py
crawler_class: arxiv_api         → app/crawlers/parsers/arxiv_api.py
crawler_class: github_api        → app/crawlers/parsers/github_api.py
crawler_class: hacker_news_api   → app/crawlers/parsers/hacker_news_api.py
crawler_class: semantic_scholar  → app/crawlers/parsers/semantic_scholar.py
crawler_class: twitter_kol       → app/crawlers/parsers/twitter_kol.py
crawler_class: twitter_search    → app/crawlers/parsers/twitter_search.py
crawler_class: hunyuan_api      → app/crawlers/parsers/hunyuan_api.py
```

**维度 → YAML 文件**：
```
national_policy → sources/national_policy.yaml (8 源, 6 启用)
beijing_policy  → sources/beijing_policy.yaml  (14 源, 10 启用)
technology      → sources/technology.yaml      (34 源, 33 启用)
talent          → sources/talent.yaml          (7 源, 4 启用)
industry        → sources/industry.yaml        (10 源, 6 启用)
universities    → sources/universities.yaml    (55 源, 46 启用)
events          → sources/events.yaml          (6 源, 4 启用)
personnel       → sources/personnel.yaml       (4 源, 4 启用)
twitter         → sources/twitter.yaml         (7 源, 7 启用, 需 API key)
                  ↳ 按 dimension 分配: technology 4源, industry 1源, talent 1源, sentiment 1源
```

**业务智能模块 (intel/)**：
```
app/api/v1/intel/router.py          → intel 子路由（聚合所有业务智能端点）
app/api/v1/intel/policy.py          → 政策智能 API (feed/opportunities/stats)
app/api/v1/intel/personnel.py       → 人事情报 API (feed/changes/stats/enriched-feed/enriched-stats)

app/services/intel/shared.py        → 共享工具（keyword_score, extract_*, load_intel_json）
app/services/intel/policy/rules.py  → 政策规则引擎（Tier 1 评分）
app/services/intel/policy/llm.py    → 政策 LLM 富化（Tier 2）
app/services/intel/policy/service.py→ 政策数据服务（读 processed JSON）
app/services/intel/personnel/rules.py  → 人事规则引擎（任免正则提取）
app/services/intel/personnel/llm.py    → 人事 LLM 富化（Tier 2，relevance/group/actionSuggestion）
app/services/intel/personnel/service.py→ 人事数据服务

app/schemas/intel/policy.py         → 政策 Pydantic schemas
app/schemas/intel/personnel.py      → 人事 Pydantic schemas（含 PersonnelChangeEnriched）

scripts/process_policy_intel.py     → 政策数据处理脚本（两级管线）
scripts/process_personnel_intel.py  → 人事数据处理脚本（规则 + --enrich LLM）

data/processed/policy_intel/        → 政策处理输出 (feed.json, opportunities.json)
data/processed/personnel_intel/     → 人事处理输出 (feed.json, changes.json, enriched_feed.json)
```

新增业务智能模块时，在 `services/intel/` 下新建子包，在 `api/v1/intel/` 添加端点，在 `intel/router.py` 注册子路由。

## 常用工作流

### 修复某个信源的选择器
```
1. 读 sources/{dim}.yaml 找到该源配置
2. 用 Playwright MCP 打开该源 URL，snapshot 分析真实 DOM 结构
3. 修改 YAML 中 selectors
4. 验证：python scripts/run_single_crawl.py --source <id>
5. 确认输出有 items_new > 0
6. 更新 docs/CrawlStatus.md 中该源的状态行
```

### 添加新标准信源
```
1. 用 Playwright MCP 打开目标网站，snapshot 分析列表页结构
2. 确定 crawl_method（static 还是 dynamic）和 CSS 选择器
3. 编辑 sources/{dim}.yaml 添加条目
4. 验证：python scripts/run_single_crawl.py --source <new_id>
5. 检查 data/raw/{dim}/{group}/{id}/ 下是否生成 JSON
6. 更新 docs/CrawlStatus.md（总览表源数 + 该维度详情表新增行）
7. 更新 docs/TODO.md（如果是待办中的信源，标记完成）
```

### 添加自定义 Parser
```
1. 在 app/crawlers/parsers/ 新建 {name}.py（继承 BaseCrawler，实现 fetch_and_parse）
2. 在 app/crawlers/registry.py 的 _CUSTOM_MAP 中添加映射
3. 在 sources/*.yaml 中配置 crawler_class: "{name}"
4. 验证：python scripts/run_single_crawl.py --source <id>
5. 更新 docs/CrawlStatus.md + docs/TODO.md
```

### 修改爬虫模板逻辑
```
1. 改 app/crawlers/templates/{type}_crawler.py
2. 验证：选 2-3 个使用该模板的源分别测试
   python scripts/run_single_crawl.py --source <id1>
   python scripts/run_single_crawl.py --source <id2>
3. ruff check app/crawlers/
4. 如影响信源状态则更新 docs/CrawlStatus.md 对应维度表
```

### 修改 API / 数据库
```
1. 改 app/api/v1/ 或 app/services/ 或 app/models/
2. 验证：uvicorn app.main:app --reload 后用 curl 或 /docs 测试
3. ruff check app/
4. 更新 docs/TODO.md 对应条目
```

### 使用 Playwright MCP 辅助开发
分析网页结构时，优先用 Playwright MCP 工具：
- `browser_navigate` → 打开目标 URL
- `browser_snapshot` → 获取页面可访问性快照（比截图更适合分析 DOM）
- 根据 snapshot 结果确定 CSS 选择器，填入 YAML

## 关键设计决策

1. **APScheduler 3.x，不用 4.x** — 4.x 是 alpha，pip 安装不到稳定版
2. **URL 归一化保留 fragment** — snapshot_crawler 用 `#snapshot-{hash}` 区分同 URL 的不同快照
3. **scheduler 启动时 auto-seed sources 到 DB** — 避免 FK violation（`manager.py`）
4. **CrawlLog 记录 crawler 创建失败** — 即使实例化出错也可通过 API 追溯
5. **RSSHub 公共实例不可用** — rsshub.app 等全部 403，需自部署或用原生 feed
6. **Article 插入用 ON CONFLICT DO NOTHING** — 避免 url_hash UNIQUE 约束冲突导致整个事务回滚（`jobs.py`）
7. **static/dynamic 共享解析逻辑** — `selector_parser.py` 提取公共函数，消除两个模板间 ~100 行重复代码
8. **业务智能模块子包结构** — `services/intel/{domain}/` 每个维度一个子包（rules + service + llm），共享工具在 `shared.py`，避免 services/ 膨胀

## 开发约定

- **Python 3.11+**，`X | Y` 联合类型
- **ruff** line-length=100，select E/F/I/W
- **async everywhere**：所有 DB、HTTP、爬虫
- 新增标准信源：只改 `sources/*.yaml`
- 新增 API 信源：`parsers/` 加类 + `registry.py` 的 `_CUSTOM_MAP` 注册
- **git add 按文件名**，不用 `git add .`

## 项目文档索引

| 文档 | 路径 | 内容 |
|------|------|------|
| 任务优先级 | `docs/TODO.md` | P0-P3 分级待办，每次完成功能后更新 |
| 爬取状态 | `docs/CrawlStatus.md` | 各维度各源的爬取状态、数据量、禁用原因 |
| 部署指南 | `docs/deployment.md` | 服务器需求、资源控制、扩容计划 |
| 院长需求 | `docs/院长智能体.md` | 前端 Dean-Agent 功能需求 |

## 常用命令

```bash
pip install -e ".[dev]"                              # 安装
uvicorn app.main:app --reload                        # 启动
python scripts/run_single_crawl.py --source <id>     # 测试单源
python scripts/run_all_crawl.py                      # 批量运行所有启用源
python scripts/process_policy_intel.py --dry-run     # 政策智能预览
python scripts/process_personnel_intel.py --dry-run  # 人事情报预览
python scripts/process_personnel_intel.py --enrich --force  # 人事 LLM 富化
ruff check app/                                      # Lint
pytest                                               # 测试
```
