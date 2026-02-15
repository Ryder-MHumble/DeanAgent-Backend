# 后续任务清单

> 最后更新: 2026-02-15 (v12: 同步文档数据 — 112 源/85 启用，detail_selectors 64 个，universities 禁用源 9 个)
> 基于前端 (Dean-Agent) 需求反推的优先级排序

---

## P0: 基础架构（已完成）

- [x] 项目骨架 (FastAPI + SQLAlchemy async + PostgreSQL + APScheduler 3.x)
- [x] 5 种模板爬虫 + 7 个自定义 Parser（全部注册）
- [x] 9 个维度 YAML 信源配置（112 源，85 启用）
- [x] v1 REST API 14 端点 (articles/sources/dimensions/health)
- [x] 调度系统 + 去重 + JSON 本地输出（data/raw/ 88 个 latest.json，覆盖模式 + is_new 标记）
- [x] Twitter 服务 + LLM 服务（OpenRouter）实现
- [x] 前端数据支撑状态文档 (crawl_status README)
- [x] 全量代码 Review（v7）— 消除 ~100 行重复代码、修复 3 个 P0 Bug、统一架构分层、优化 http_client/playwright_pool

### ⚠️ 已回退删除

- ~~v2 业务 API（13 端点 + schemas + business services）~~ — 代码已删除，需重新规划
- ~~API 设计文档 (docs/api_design/README.md)~~ — 随 v2 一起删除

---

## P1: 高优先级（直接影响前端功能）

### 信源补充
- [ ] 新增「领导讲话」信源 — gov.cn 国务院领导活动页 + 部委领导讲话
- [ ] 恢复 bjfgw_policy (改用 dynamic 方法)
- [ ] 恢复 thepaper_tech (解析 __NEXT_DATA__ JSON)
- [ ] 恢复 huxiu_news (寻找 RSS feed 或 API)

### LLM 集成
- [ ] 配置 .env OPENROUTER_API_KEY + TWITTER_API_KEY
- [ ] 重新规划业务 API 层（v2 代码已删除，需决定是否重建）

### 数据质量
- [x] ~~详情页内容抓取~~ — 已为 64 个启用信源配置 detail_selectors（universities 44, beijing_policy 7, national_policy 4, industry 3, talent 3, personnel 3），可自动抓取详情页正文。v11 修复 10 个源的错误选择器，新增 4 源。
- [x] ~~修复详情页 URL 404 问题~~ — selector_parser.py 增加 `_normalize_base_url()` 防止 urljoin 丢失路径段；修复 9 个源的 base_url 配置
- [x] ~~修复 title-only 源~~ — v11: 修复 bnu/ruc/jlu/sustech/slai 错误选择器，修复 uestc_news 列表选择器，修复 moe_renshi/si/talent TRS_UEDITOR→TRS_Editor，修复 jyb_news URL 空格 bug，新增 nosta/moe_keji/beijing_jw/nature_index detail_selectors
- [ ] 人事变动 LLM 提取 — 从标题中提取人名、原职位、新职位

---

## P2: 中优先级（扩展覆盖范围）

### 信源扩展
- [ ] Semantic Scholar API 扩展 — 支持 KOL 追踪 (hIndex, 论文数)
- [ ] ArXiv affiliation 变更检测 — 人才回流信号
- [ ] IT桔子/企查查 — 更全面投融资数据
- [ ] 补充高校 HR/组织部页面 (15 所, snapshot 模式)
- [ ] 补充 AI 院系官网 (8 个)
- [ ] IEEE Fellow / ACM Fellow 年度公告源
- [ ] 微信公众号方案（搜狗微信搜索 / 公号后台）

### 业务 API（阻塞：v2 基础层已删除，需先完成 P1 "重新规划业务 API"）
- [ ] 政策机会匹配 (LLM)
- [ ] 学术流动分析 (LLM)
- [ ] 内参机会推荐 (LLM)

### 数据处理
- [ ] refined/ 数据管线 — 定时将 raw 数据经 LLM 处理后存入 refined/
- [ ] 缓存层 — LLM 处理结果缓存，避免重复调用

---

## P3: 低优先级（锦上添花）

### 信源
- [ ] 创建 sentiment 维度 YAML (社交媒体，难度最高)
- [ ] 青塔 (Nuxt SPA，需 Playwright 深度适配)
- [ ] CNIPA 专利公告
- [ ] 修复 universities 禁用源 (zju, nju, bupt, nankai, nwpu, scu, lzu, zhejianglab, shanghairanking)

### 基础设施
- [ ] Alembic 数据库迁移
- [x] ~~代码重复消除~~ — selector_parser.py 提取共享逻辑、http_client 重试函数统一
- [x] ~~Article IntegrityError 修复~~ — 改用 ON CONFLICT DO NOTHING
- [x] ~~CORS 配置修复~~ — 去掉无效 allow_credentials
- [x] ~~架构分层统一~~ — dimension_service.py、删除冗余 get_db_session、删除死字段 q
- [x] ~~Playwright 并发控制~~ — semaphore 限制 MAX_CONTEXTS
- [x] ~~sort_by 白名单~~ — 防止任意列名注入
- [ ] 单元测试 / 集成测试
- [ ] WebSocket 实时推送
- [ ] 部署验证 (Render)

---

## 不在爬虫范畴的模块

以下前端模块需要内部系统对接，不属于爬虫项目范围：

| 模块 | 所需系统 |
|------|---------|
| 院内管理 - 财务 | 内部财务系统 |
| 院内管理 - 项目督办 | 内部 OA/项目管理 |
| 院内管理 - 学生事务 | 学生信息系统 |
| 院内管理 - 舆情安全 | 舆情监测平台 (需 sentiment 维度 + 内部系统) |
| 院内管理 - 中心绩效 | 内部 KPI 系统 |
| 人脉网络 - 关系维护 | CRM 系统 |
| 人脉网络 - 社交行动 | CRM + 日历 |
| 智能日程 - 日程管理 | 飞书/Outlook 日历 API |
| 智能日程 - 邀约评估 | 日历 + 爬虫活动数据 |
| 智能日程 - 冲突化解 | 日历 API |
