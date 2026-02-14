# 后续任务清单

> 最后更新: 2026-02-13
> 基于前端 (Dean-Agent) 需求反推的优先级排序

---

## P0: 已完成 ✅

- [x] v2 业务 API 基础架构 (json_reader, llm_service, schemas, routes)
- [x] 13 个 v2 API 端点实现 (Phase 1 规则处理 + Phase 2 LLM 增强)
- [x] API 设计文档 (docs/api_design/README.md)
- [x] 前端数据支撑状态文档 (crawl_status README 新增章节)

---

## P1: 高优先级（直接影响前端功能）

### 信源补充
- [ ] 新增「领导讲话」信源 — gov.cn 国务院领导活动页 + 部委领导讲话
- [ ] 恢复 bjfgw_policy (改用 dynamic 方法)
- [ ] 恢复 thepaper_tech (解析 __NEXT_DATA__ JSON)
- [ ] 恢复 huxiu_news (寻找 RSS feed 或 API)

### LLM 集成
- [ ] 配置 .env OPENROUTER_API_KEY
- [ ] 验证 LLM 增强端点: /tech/trends, /briefing/daily, /policy?enhanced=true

### 数据质量
- [ ] 详情页内容抓取 — 当前只有标题+URL，content/summary 为空
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

### v2 API 扩展
- [ ] /api/v2/policy/opportunities — 政策机会匹配 (LLM)
- [ ] /api/v2/talent/mobility — 学术流动 (LLM)
- [ ] /api/v2/tech/opportunities — 内参机会 (LLM)

### 数据处理
- [ ] refined/ 数据管线 — 定时将 raw 数据经 LLM 处理后存入 refined/
- [ ] 缓存层 — LLM 处理结果缓存，避免重复调用

---

## P3: 低优先级（锦上添花）

### 信源
- [ ] 创建 sentiment 维度 YAML (社交媒体，难度最高)
- [ ] 青塔 (Nuxt SPA，需 Playwright 深度适配)
- [ ] CNIPA 专利公告
- [ ] 修复 universities 禁用源 (zju, nju, zhejianglab, shanghairanking)

### 基础设施
- [ ] Alembic 数据库迁移
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
