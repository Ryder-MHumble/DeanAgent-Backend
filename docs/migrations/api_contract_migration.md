# API Contract Migration

更新时间：`2026-04-08`

范围：`jobs` 资源化 + `students` 资源边界收敛。

目标：

- 不打断现有 Dean-Agent / ScholarDB / Athena / NanoBot 调用。
- 不破坏现有数仓与 BI 口径。
- 为后续统一任务审计与重试/追踪能力预留最小建模空间。

## 1. 数据契约影响矩阵

| 主题 | 当前主口径 | 受影响对象 | 迁移原则 |
|---|---|---|---|
| 爬取运行状态 | `source_states` | 信源目录、健康页、高校信源页 | 保持不变，继续提供 latest snapshot |
| 爬取日志 | `crawl_logs` | source 日志页、24h 爬取统计、console | 保持不变，继续提供 source 维度事实 |
| 统一任务审计 | 无统一表；分散在 action 端点、scheduler、专用 status 接口 | 前端轮询、平台审计、失败重试 | 新增 `jobs` 资源，先加法，不要求首期替换旧口径 |
| 学生主数据 | `supervised_students` | `/students`、机构学生数、学者详情学生数 | 保持单表主事实，不拆分为 scholar 子表 |
| 导师维表 | `scholars` | 导师解析、导师详情、导师名下学生数 | 保持维表定位，通过 `scholar_id` 关联学生事实 |

## 2. 对现有 BI / 报表字段的影响

第一阶段不建议改动以下字段来源：

- 爬取健康类：
  - `source_states.last_crawl_at`
  - `source_states.consecutive_failures`
  - `source_states.is_enabled_override`
  - `crawl_logs.status`
  - `crawl_logs.items_total`
  - `crawl_logs.items_new`
  - `crawl_logs.started_at`
  - `crawl_logs.finished_at`
- 学生类：
  - `supervised_students.enrollment_year`
  - `supervised_students.home_university`
  - `supervised_students.status`
  - `supervised_students.scholar_id`
- 学者/机构派生类：
  - 学者详情的 `supervised_students_count`
  - 机构详情的 `student_count_24` / `student_count_25` / `student_count_total`

结论：

- `jobs` 资源是新增审计面，不应在首期替换现有 BI 事实源。
- `students` 资源收敛是 API ownership 调整，不应触发 `supervised_students` 拆表或字段重命名。

## 3. 前后兼容策略

### 3.1 老端点可用周期

建议以下 action 型端点在 `jobs` 资源正式上线后继续保留到 `2026-12-31`：

- `POST /api/sources/{source_id}/trigger`
- `POST /api/crawler/start`
- `GET /api/crawler/status`
- `POST /api/crawler/stop`
- `POST /api/health/pipeline-trigger`
- `POST /api/intel/paper-transfer/run`
- 相关专用 `status/results` 查询端点

建议以下 scholar-scoped 学生端点继续保留到 `2026-12-31`：

- `GET /api/scholars/{url_hash}/students`
- `POST /api/scholars/{url_hash}/students`
- `GET /api/scholars/{url_hash}/students/{student_id}`
- `PATCH /api/scholars/{url_hash}/students/{student_id}`
- `DELETE /api/scholars/{url_hash}/students/{student_id}`

### 3.2 老字段可用周期

建议以下旧口径字段至少保留到 `2027-03-31`，不要与端点下线绑定在同一批：

- `source_states.*` 现有健康/启停字段
- `crawl_logs.*` 现有 source 级运行字段
- `supervised_students.*` 现有学生事实字段

原因：

- 前端切到 `jobs` 只解决 API 轮询问题，不等于数仓已完成事实表切换。
- BI 和数据同步通常滞后于前端改造，必须给至少一个完整报表周期做双跑校验。

## 4. 建议切换顺序

1. API 先新增 `jobs` 资源，旧 action 端点改为兼容入口。
2. 服务层做双写或双映射：
   - 旧逻辑继续写 `source_states` 与 `crawl_logs`
   - 新逻辑额外写 `crawl_jobs` / `crawl_job_events`，或先在应用层组装
3. 前端先切运行态查询：
   - 新触发返回 `job_id`
   - 轮询改查 `/jobs/{job_id}` 与 `/jobs/{job_id}/events`
4. 数据同步再补任务事实：
   - 新增 `fct_crawl_jobs` / `fct_crawl_job_events`
   - 旧健康报表继续从 `source_states` / `crawl_logs` 出数
5. 学生资源最后收敛：
   - `/students` 成为唯一主资源
   - scholar-scoped students 仅保留兼容视图/兼容写入口
6. 双跑稳定后，再冻结旧 action 端点与 scholar-scoped students 写路径。

## 5. 最小数据建模建议

以下是 future schema 草案，不要求本轮立即建表。

### 5.1 `crawl_jobs`

建议字段：

- `job_id uuid primary key`
- `job_type text not null`
  - 建议枚举：`crawl_source` / `crawl_batch` / `pipeline_daily` / `paper_transfer` / `report_generate`
- `resource_type text null`
  - 建议枚举：`source` / `source_group` / `pipeline` / `report`
- `resource_id text null`
- `request_origin text not null`
  - 建议枚举：`api` / `scheduler` / `console` / `internal`
- `requested_by text null`
- `idempotency_key text null`
- `status text not null`
  - 建议枚举：`queued` / `running` / `succeeded` / `failed` / `cancelled`
- `submitted_at timestamptz not null`
- `started_at timestamptz null`
- `finished_at timestamptz null`
- `duration_ms integer null`
- `priority smallint not null default 0`
- `source_count integer null`
- `items_total integer null`
- `items_new integer null`
- `error_code text null`
- `error_message text null`
- `correlation_id text null`
- `request_payload jsonb not null default '{}'::jsonb`
- `result_payload jsonb not null default '{}'::jsonb`
- `retry_of_job_id uuid null`

建议索引：

- `pk_crawl_jobs(job_id)`
- `idx_crawl_jobs_type_time(job_type, submitted_at desc)`
- `idx_crawl_jobs_resource(resource_type, resource_id, submitted_at desc)`
- `idx_crawl_jobs_status_time(status, submitted_at desc)`
- `uq_crawl_jobs_idempotency(idempotency_key)` where `idempotency_key is not null`

### 5.2 `crawl_job_events`

建议字段：

- `event_id bigserial primary key`
- `job_id uuid not null`
- `seq integer not null`
- `event_type text not null`
  - 建议枚举：`queued` / `started` / `progress` / `source_started` / `source_finished` / `failed` / `completed`
- `event_at timestamptz not null`
- `source_id text null`
- `status text null`
- `message text null`
- `metrics jsonb not null default '{}'::jsonb`
- `payload jsonb not null default '{}'::jsonb`

建议约束与索引：

- `fk_crawl_job_events_job(job_id -> crawl_jobs.job_id)`
- `uq_crawl_job_events_seq(job_id, seq)`
- `idx_crawl_job_events_job_time(job_id, event_at)`
- `idx_crawl_job_events_source_time(source_id, event_at desc)`
- `idx_crawl_job_events_type_time(event_type, event_at desc)`

## 6. students 资源边界收敛建议

最小调整建议：

- `supervised_students` 继续做唯一主事实表。
- `/api/students` 作为唯一 canonical collection。
- 若需要承接导师视角，优先给 `/students` 增加显式过滤参数：
  - `scholar_id`
  - 或 `mentor_id`
- `/api/scholars/{url_hash}/students` 在兼容期内只作为 projection，不再承担主 ownership。

不要做的事：

- 不新增 `scholar_students` 之类镜像表。
- 不把学生数组重新嵌回 `scholars` 作为主存储。
- 不让机构学生统计改从 scholar-scoped API 回流计算。

## 7. 实施完成判定

- 前端已能基于 `job_id` 查询任务状态与事件。
- `source_states` / `crawl_logs` 现有报表不回归。
- `supervised_students` 相关报表口径不变化。
- scholar-scoped students 调用量已可观测，且新流量默认走 `/students`。
- 旧端点 sunset 日期、切换顺序、数据口径说明已同步到 API 文档。
