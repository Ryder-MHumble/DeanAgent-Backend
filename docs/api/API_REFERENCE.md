# API 参考总览

- 生成时间（UTC）：`2026-04-08 07:06:30Z`
- API 路由总数：`143`
- Method 分布：`DELETE` 10、`GET` 97、`PATCH` 12、`POST` 24
- 信源总数：`268`
- 启用信源：`191`

## 服务清单

| 服务 | 路由数 | 典型用途 |
|---|---:|---|
| `scholars` | 17 | scholars |
| `events` | 14 | events |
| `sources` | 11 | sources |
| `institutions` | 10 | institutions |
| `crawler` | 8 | crawler-control |
| `projects` | 8 | projects |
| `students` | 7 | students |
| `venues` | 7 | venues |
| `llm-tracking` | 6 | llm-tracking |
| `articles` | 5 | articles |
| `intel/personnel` | 5 | intel / personnel-intel |
| `intel/tech-frontier` | 5 | intel / tech-frontier |
| `intel/university` | 5 | intel / university-eco |
| `health` | 4 | health |
| `social-kol` | 4 | social-kol |
| `social-posts` | 4 | social-posts |
| `aminer` | 3 | aminer |
| `intel/daily-briefing` | 3 | daily-briefing / intel |
| `intel/paper-transfer` | 3 | intel / paper-transfer |
| `intel/policy` | 3 | intel / policy-intel |
| `leadership` | 3 | leadership |
| `reports` | 3 | reports |
| `sentiment` | 3 | sentiment |
| `dimensions` | 2 | dimensions |

## 信源维度覆盖

| 维度 | 中文名 | 总数 | 启用 |
|---|---|---:|---:|
| `universities` | 高校与科研生态 | 84 | 74 |
| `personnel` | 组织人事动态 | 54 | 54 |
| `scholars` | 学者与师资库 | 49 | 0 |
| `technology` | 技术前沿与创新 | 34 | 27 |
| `beijing_policy` | 北京市政策治理 | 16 | 15 |
| `industry` | 产业与投融资 | 10 | 6 |
| `national_policy` | 国家政策治理 | 8 | 8 |
| `talent` | 人才与学术发展 | 7 | 4 |
| `events` | 学术会议与活动 | 6 | 3 |

## 信源分组 TOP 20

| group | 数量 |
|---|---:|
| `university_news` | 61 |
| `university_leadership_official` | 50 |
| `policy` | 24 |
| `tsinghua` | 13 |
| `company_blogs` | 12 |
| `ai_institutes` | 11 |
| `pku` | 9 |
| `academic` | 8 |
| `news` | 8 |
| `international_media` | 7 |
| `nju` | 5 |
| `sjtu` | 5 |
| `ustc` | 5 |
| `cn_ai_company` | 5 |
| `provincial` | 5 |
| `tracking` | 4 |
| `community` | 4 |
| `awards` | 4 |
| `news_personnel` | 3 |
| `cas_iscas` | 3 |

## 信源标签 TOP 30

| tag | 数量 |
|---|---:|
| `university` | 111 |
| `personnel` | 55 |
| `official` | 51 |
| `leadership` | 50 |
| `faculty` | 49 |
| `news` | 44 |
| `auto` | 29 |
| `ai` | 26 |
| `policy` | 25 |
| `company_blog` | 17 |
| `cs` | 16 |
| `985` | 16 |
| `academic` | 15 |
| `tsinghua` | 15 |
| `211` | 13 |
| `education` | 11 |
| `institute` | 11 |
| `pku` | 10 |
| `cas` | 9 |
| `tech_media` | 9 |
| `industry` | 8 |
| `nju` | 7 |
| `se` | 7 |
| `international` | 7 |
| `domestic` | 6 |
| `sjtu` | 6 |
| `ustc` | 6 |
| `bjkw` | 5 |
| `science` | 5 |
| `beijing` | 5 |

## Deprecated 路由

| Method | 路径 | 替代接口 | Sunset |
|---|---|---|---|
| `GET` | `/api/v1/articles/search` | `/api/v1/articles` | `2026-12-31` |
| `GET` | `/api/v1/crawler/download` | `-` | `2026-12-31` |
| `POST` | `/api/v1/crawler/start` | `-` | `2026-12-31` |
| `GET` | `/api/v1/crawler/status` | `-` | `2026-12-31` |
| `POST` | `/api/v1/crawler/stop` | `-` | `2026-12-31` |
| `GET` | `/api/v1/scholars/{url_hash}/students` | `-` | `2026-12-31` |
| `POST` | `/api/v1/scholars/{url_hash}/students` | `-` | `2026-12-31` |
| `DELETE` | `/api/v1/scholars/{url_hash}/students/{student_id}` | `-` | `2026-12-31` |
| `GET` | `/api/v1/scholars/{url_hash}/students/{student_id}` | `-` | `2026-12-31` |
| `PATCH` | `/api/v1/scholars/{url_hash}/students/{student_id}` | `-` | `2026-12-31` |
| `POST` | `/api/v1/scholars/{url_hash}/updates` | `-` | `2026-12-31` |
| `DELETE` | `/api/v1/scholars/{url_hash}/updates/{update_idx}` | `-` | `2026-12-31` |
| `GET` | `/api/v1/social-posts/search` | `/api/v1/social-posts` | `2026-12-31` |

## Agent 调用快捷映射

| 用户意图 | 推荐接口 | 参数建议 |
|---|---|---|
| 快速看全部信源结构 | `GET /api/v1/sources/catalog` | `include_facets=true&page_size=200` |
| 快速定位信源 ID | `GET /api/v1/sources/resolve` | `q=人社局` 或 `q=清华` |
| 查询高校领导信源 | `GET /api/v1/sources/catalog` | `tag=leadership` 或 `group=university_leadership_official` |
| 查询学者/师资信源 | `GET /api/v1/sources/catalog` | `dimension=scholars` 或 `tag=faculty` |
| 按单个/多个信源直接拉取数据 | `GET /api/v1/sources/items` | `source_id=...` 或 `source_name=...`，配合 `page/page_size` 翻页 |
| 按路径固定某个信源拉取数据 | `GET /api/v1/sources/{source_id}/items` | `date_from/date_to/keyword/page/page_size` |
| 查询共建导师/两院关系学者 | `GET /api/v1/scholars` | `is_adjunct_supervisor=true` 或 `project_subcategory=兼职导师` |
| 查询两院学生名单 | `GET /api/v1/students` | `institution=...`、`mentor_name=...`、`enrollment_year=...` |

## 路由明细

### `aminer`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/aminer/organizations` | `aminer` | 查询机构信息 |
| `GET` | `/api/v1/aminer/scholars/search` | `aminer` | 搜索学者基础信息 |
| `GET` | `/api/v1/aminer/scholars/{aminer_id}` | `aminer` | 获取学者详细信息 |

### `articles`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/articles` | `articles` | 文章列表 |
| `GET` | `/api/v1/articles/search` | `articles` | 全文搜索（deprecated） |
| `GET` | `/api/v1/articles/stats` | `articles` | 文章统计 |
| `GET` | `/api/v1/articles/{article_id}` | `articles` | 文章详情 |
| `PATCH` | `/api/v1/articles/{article_id}` | `articles` | 更新文章 |

### `crawler`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/crawler/download` | `crawler-control` | 下载爬取结果（deprecated） |
| `POST` | `/api/v1/crawler/jobs` | `crawler-control` | 创建手动爬取任务 |
| `GET` | `/api/v1/crawler/jobs/{job_id}` | `crawler-control` | 查询手动爬取任务状态 |
| `POST` | `/api/v1/crawler/jobs/{job_id}/cancel` | `crawler-control` | 取消手动爬取任务 |
| `GET` | `/api/v1/crawler/jobs/{job_id}/result` | `crawler-control` | 下载指定手动爬取任务结果 |
| `POST` | `/api/v1/crawler/start` | `crawler-control` | 启动爬取任务（deprecated） |
| `GET` | `/api/v1/crawler/status` | `crawler-control` | 获取爬取状态（deprecated） |
| `POST` | `/api/v1/crawler/stop` | `crawler-control` | 停止爬取任务（deprecated） |

### `dimensions`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/dimensions` | `dimensions` | 维度列表 |
| `GET` | `/api/v1/dimensions/{dimension}` | `dimensions` | 维度文章 |

### `events`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/events` | `events` | 活动列表 |
| `POST` | `/api/v1/events` | `events` | 创建活动 |
| `POST` | `/api/v1/events/batch` | `events` | 批量创建活动 |
| `GET` | `/api/v1/events/stats` | `events` | 活动统计 |
| `GET` | `/api/v1/events/taxonomy` | `events` | 获取三级分类树 |
| `POST` | `/api/v1/events/taxonomy` | `events` | 新增分类节点 |
| `DELETE` | `/api/v1/events/taxonomy/{node_id}` | `events` | 删除分类节点 |
| `PATCH` | `/api/v1/events/taxonomy/{node_id}` | `events` | 更新分类节点 |
| `DELETE` | `/api/v1/events/{event_id}` | `events` | 删除活动 |
| `GET` | `/api/v1/events/{event_id}` | `events` | 活动详情 |
| `PATCH` | `/api/v1/events/{event_id}` | `events` | 更新活动 |
| `GET` | `/api/v1/events/{event_id}/scholars` | `events` | 获取活动关联的学者列表 |
| `POST` | `/api/v1/events/{event_id}/scholars` | `events` | 添加学者关联 |
| `DELETE` | `/api/v1/events/{event_id}/scholars/{scholar_id}` | `events` | 移除学者关联 |

### `health`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/health` | `health` | 系统健康检查 |
| `GET` | `/api/v1/health/crawl-status` | `health` | 爬取健康概览 |
| `GET` | `/api/v1/health/pipeline-status` | `health` | 管线状态 |
| `POST` | `/api/v1/health/pipeline-trigger` | `health` | 手动触发管线 |

### `institutions`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/institutions` | `institutions` | 机构列表（统一接口） |
| `POST` | `/api/v1/institutions` | `institutions` | 创建机构（支持简化模式） |
| `GET` | `/api/v1/institutions/aminer/search-org` | `institutions` | 搜索 AMiner 机构名 |
| `GET` | `/api/v1/institutions/search` | `institutions` | 搜索机构（模糊匹配） |
| `GET` | `/api/v1/institutions/stats` | `institutions` | 机构统计 |
| `GET` | `/api/v1/institutions/suggest` | `institutions` | 建议机构匹配 |
| `GET` | `/api/v1/institutions/taxonomy` | `institutions` | 分类体系统计 |
| `DELETE` | `/api/v1/institutions/{institution_id}` | `institutions` | 删除机构 |
| `GET` | `/api/v1/institutions/{institution_id}` | `institutions` | 机构详情 |
| `PATCH` | `/api/v1/institutions/{institution_id}` | `institutions` | 更新机构 |

### `intel/daily-briefing`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/intel/daily-briefing/metrics` | `intel,daily-briefing` | 获取早报指标卡片 |
| `GET` | `/api/v1/intel/daily-briefing/report` | `intel,daily-briefing` | 获取 AI 早报 |
| `GET` | `/api/v1/intel/daily-briefing/today` | `intel,daily-briefing` | 获取今日 AI 早报（兼容路径） |

### `intel/paper-transfer`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/intel/paper-transfer/results` | `intel,paper-transfer` | 获取论文转化分析结果 |
| `POST` | `/api/v1/intel/paper-transfer/run` | `intel,paper-transfer` | 触发论文转化分析 Pipeline |
| `GET` | `/api/v1/intel/paper-transfer/status` | `intel,paper-transfer` | 查询 Pipeline 运行状态 |

### `intel/personnel`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/intel/personnel/changes` | `intel,personnel-intel` | 结构化任免变动 |
| `GET` | `/api/v1/intel/personnel/enriched-feed` | `intel,personnel-intel` | LLM 富化人事动态 |
| `GET` | `/api/v1/intel/personnel/enriched-stats` | `intel,personnel-intel` | 富化数据统计 |
| `GET` | `/api/v1/intel/personnel/feed` | `intel,personnel-intel` | 人事动态 Feed |
| `GET` | `/api/v1/intel/personnel/stats` | `intel,personnel-intel` | 人事统计 |

### `intel/policy`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/intel/policy/feed` | `intel,policy-intel` | 政策动态 Feed |
| `GET` | `/api/v1/intel/policy/opportunities` | `intel,policy-intel` | 政策机会看板 |
| `GET` | `/api/v1/intel/policy/stats` | `intel,policy-intel` | 政策统计 |

### `intel/tech-frontier`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/intel/tech-frontier/opportunities` | `intel,tech-frontier` | 科技前沿机会列表 |
| `GET` | `/api/v1/intel/tech-frontier/signals` | `intel,tech-frontier` | 扁平信号流 |
| `GET` | `/api/v1/intel/tech-frontier/stats` | `intel,tech-frontier` | 科技前沿 KPI 统计 |
| `GET` | `/api/v1/intel/tech-frontier/topics` | `intel,tech-frontier` | 科技前沿主题列表 |
| `GET` | `/api/v1/intel/tech-frontier/topics/{topic_id}` | `intel,tech-frontier` | 单个主题详情 |

### `intel/university`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/intel/university/article/{url_hash}` | `intel,university-eco` | 高校文章详情 |
| `GET` | `/api/v1/intel/university/feed` | `intel,university-eco` | 高校动态 Feed |
| `GET` | `/api/v1/intel/university/overview` | `intel,university-eco` | 高校生态总览 |
| `GET` | `/api/v1/intel/university/research` | `intel,university-eco` | 高校科研成果 |
| `GET` | `/api/v1/intel/university/sources` | `intel,university-eco` | 高校信源列表 |

### `leadership`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/leadership` | `leadership` | 高校领导列表 |
| `GET` | `/api/v1/leadership/all` | `leadership` | 高校领导全量数据 |
| `GET` | `/api/v1/leadership/{institution_id}` | `leadership` | 高校领导当前数据 |

### `llm-tracking`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/llm-tracking/audit-trail` | `llm-tracking` |  |
| `GET` | `/api/v1/llm-tracking/calls-by-article/{article_id}` | `llm-tracking` |  |
| `GET` | `/api/v1/llm-tracking/calls-by-stage/{stage}` | `llm-tracking` |  |
| `GET` | `/api/v1/llm-tracking/cost-by-model` | `llm-tracking` |  |
| `GET` | `/api/v1/llm-tracking/health` | `llm-tracking` |  |
| `GET` | `/api/v1/llm-tracking/summary` | `llm-tracking` |  |

### `projects`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/projects` | `projects` | 项目列表 |
| `POST` | `/api/v1/projects` | `projects` | 创建项目 |
| `POST` | `/api/v1/projects/batch` | `projects` | 批量创建项目 |
| `GET` | `/api/v1/projects/stats` | `projects` | 项目统计 |
| `GET` | `/api/v1/projects/taxonomy` | `projects` | 项目分类树 |
| `DELETE` | `/api/v1/projects/{project_id}` | `projects` | 删除项目 |
| `GET` | `/api/v1/projects/{project_id}` | `projects` | 项目详情 |
| `PATCH` | `/api/v1/projects/{project_id}` | `projects` | 更新项目 |

### `reports`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/reports/dimensions` | `reports` |  |
| `POST` | `/api/v1/reports/generate` | `reports` |  |
| `GET` | `/api/v1/reports/sentiment/latest` | `reports` |  |

### `scholars`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/scholars` | `scholars` | 学者列表 |
| `POST` | `/api/v1/scholars` | `scholars` | 手动创建学者 |
| `POST` | `/api/v1/scholars/batch` | `scholars` | JSON 批量创建学者 |
| `POST` | `/api/v1/scholars/import` | `scholars` | Excel/CSV 批量导入学者 |
| `GET` | `/api/v1/scholars/stats` | `scholars` | 学者统计 |
| `DELETE` | `/api/v1/scholars/{url_hash}` | `scholars` | 删除学者记录 |
| `GET` | `/api/v1/scholars/{url_hash}` | `scholars` | 学者详情 |
| `PATCH` | `/api/v1/scholars/{url_hash}/achievements` | `scholars` | 更新学术成就 |
| `PATCH` | `/api/v1/scholars/{url_hash}/basic` | `scholars` | 更新基础信息 |
| `PATCH` | `/api/v1/scholars/{url_hash}/relation` | `scholars` | 更新与两院关系 |
| `GET` | `/api/v1/scholars/{url_hash}/students` | `scholars` | 查询指导学生列表（deprecated） |
| `POST` | `/api/v1/scholars/{url_hash}/students` | `scholars` | 新增指导学生（deprecated） |
| `DELETE` | `/api/v1/scholars/{url_hash}/students/{student_id}` | `scholars` | 删除学生记录（deprecated） |
| `GET` | `/api/v1/scholars/{url_hash}/students/{student_id}` | `scholars` | 查询单名学生详情（deprecated） |
| `PATCH` | `/api/v1/scholars/{url_hash}/students/{student_id}` | `scholars` | 更新学生信息（deprecated） |
| `POST` | `/api/v1/scholars/{url_hash}/updates` | `scholars` | 新增用户备注动态（已停用）（deprecated） |
| `DELETE` | `/api/v1/scholars/{url_hash}/updates/{update_idx}` | `scholars` | 删除用户备注动态（已停用）（deprecated） |

### `sentiment`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/sentiment/content/{content_id}` | `sentiment` | 内容详情 + 评论 |
| `GET` | `/api/v1/sentiment/feed` | `sentiment` | 社媒内容信息流 |
| `GET` | `/api/v1/sentiment/overview` | `sentiment` | 舆情概览统计 |

### `social-kol`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/social-kol/accounts` | `social-kol` | 账号列表 |
| `POST` | `/api/v1/social-kol/ingest/twitter` | `social-kol` | 导入 Twitter/KOL 聚合数据 |
| `GET` | `/api/v1/social-kol/posts` | `social-kol` | 帖子列表 |
| `GET` | `/api/v1/social-kol/posts/{platform}/{external_post_id}` | `social-kol` | 帖子详情（含热门回复） |

### `social-posts`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/social-posts` | `social-posts` | 社媒帖子列表 |
| `GET` | `/api/v1/social-posts/search` | `social-posts` | 社媒帖子搜索（deprecated） |
| `GET` | `/api/v1/social-posts/stats` | `social-posts` | 社媒帖子统计 |
| `GET` | `/api/v1/social-posts/{post_id}` | `social-posts` | 社媒帖子详情 |

### `sources`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/sources` | `sources` | 信源列表 |
| `GET` | `/api/v1/sources/catalog` | `sources` | 信源目录（分页 + 分面） |
| `GET` | `/api/v1/sources/deprecations` | `sources` | API 弃用迁移表 |
| `GET` | `/api/v1/sources/facets` | `sources` | 信源筛选分面 |
| `GET` | `/api/v1/sources/items` | `sources` | 按信源取数据（统一入口） |
| `GET` | `/api/v1/sources/resolve` | `sources` | 信源解析与直连入口 |
| `GET` | `/api/v1/sources/{source_id}` | `sources` | 信源详情 |
| `PATCH` | `/api/v1/sources/{source_id}` | `sources` | 启用/禁用信源 |
| `GET` | `/api/v1/sources/{source_id}/items` | `sources` | 单个信源数据流 |
| `GET` | `/api/v1/sources/{source_id}/logs` | `sources` | 爬取日志 |
| `POST` | `/api/v1/sources/{source_id}/trigger` | `sources` | 手动触发爬取 |

### `students`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/students` | `students` | 学生列表 |
| `POST` | `/api/v1/students` | `students` | 新增学生 |
| `GET` | `/api/v1/students/by-scholar/{scholar_id}` | `students` | 按导师查询学生 |
| `GET` | `/api/v1/students/options` | `students` | 学生筛选项 |
| `DELETE` | `/api/v1/students/{student_id}` | `students` | 删除学生 |
| `GET` | `/api/v1/students/{student_id}` | `students` | 学生详情 |
| `PATCH` | `/api/v1/students/{student_id}` | `students` | 更新学生 |

### `venues`

| Method | Path | Tags | Summary |
|---|---|---|---|
| `GET` | `/api/v1/venues` | `venues` | 获取顶会/期刊列表 |
| `POST` | `/api/v1/venues` | `venues` | 创建顶会/期刊 |
| `POST` | `/api/v1/venues/batch` | `venues` | 批量导入顶会/期刊 |
| `GET` | `/api/v1/venues/stats` | `venues` | 顶会/期刊统计 |
| `DELETE` | `/api/v1/venues/{venue_id}` | `venues` | 删除顶会/期刊 |
| `GET` | `/api/v1/venues/{venue_id}` | `venues` | 获取顶会/期刊详情 |
| `PATCH` | `/api/v1/venues/{venue_id}` | `venues` | 更新顶会/期刊 |

## 校验说明

- 本文档由 `scripts/core/generate_api_docs.py` 自动生成。
- 若接口变更，请重新执行：`./.venv/bin/python scripts/core/generate_api_docs.py`。
