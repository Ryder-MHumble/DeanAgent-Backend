# 部署架构与方案

> 最后更新: 2026-02-17

## 部署目标

将信息监测系统做成**钉钉应用 + 钉钉机器人**，供院长和内部人员使用。核心约束：

| 约束 | 原因 |
|------|------|
| 必须国内可达 | 钉钉回调/H5 应用不能走 VPN |
| 需要访问部分海外站点 | ArXiv、GitHub、HackerNews、Twitter 等信源 |
| 需要 LLM 能力 | 政策智能 Tier 2 富化、机器人问答 |
| 需要访问钉钉内部数据 | 通讯录、日程、知识库 |

---

## 推荐方案：国内服务器 + 国产 LLM（单机全栈）

这是**最简单、延迟最低、成本最低**的方案。

```
┌─────────────────────────────────────────────────────┐
│               国内云服务器（阿里云/腾讯云）              │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐ │
│  │ FastAPI   │  │ 爬虫引擎  │  │ APScheduler 调度  │ │
│  │ (API+Bot) │  │ +Playwright│  │                   │ │
│  └────┬─────┘  └────┬─────┘  └───────────────────┘ │
│       │              │                               │
│  ┌────┴──────────────┴─────┐                        │
│  │   PostgreSQL（本机）      │                        │
│  └──────────────────────────┘                        │
└──────────┬────────────────────────┬─────────────────┘
           │                        │
     ┌─────┴─────┐          ┌──────┴──────┐
     │ 钉钉开放平台 │          │ 国产 LLM API │
     │ (Stream)   │          │ (DeepSeek等) │
     └───────────┘          └─────────────┘
```

### 为什么这个方案最好

1. **数据库在本机** — 查询延迟 <1ms，而 Supabase（海外）从国内访问 200-400ms/次，数据量大了不可用
2. **国产 LLM 替代 OpenRouter** — DeepSeek API / 通义千问 从国内调用延迟 <100ms，效果不输 Gemini Flash，价格更低
3. **钉钉 Stream 模式** — 机器人通过长连接接收消息，不需要公网回调地址，部署简单
4. **单机部署** — 86 个启用源的规模，一台 2 核 4G 服务器完全够用

### LLM 替换方案

当前用 OpenRouter (Gemini Flash)，建议替换为：

| 方案 | API | 价格 | 国内延迟 | 推荐度 |
|------|-----|------|---------|--------|
| **DeepSeek** | `api.deepseek.com` | ¥1/M tokens | ~50ms | 推荐，性价比最高 |
| 通义千问 | 阿里云 DashScope | ¥0.8/M tokens | ~30ms | 阿里云用户优先 |
| GLM-4 | `open.bigmodel.cn` | ¥1/M tokens | ~60ms | 中文效果好 |

改动量极小：只需修改 `app/services/intel/policy/llm.py` 和 `app/services/intel/personnel/llm.py` 中的 API 调用，接口兼容 OpenAI 格式。

---

## 数据库方案对比

| 方案 | 延迟 | 成本 | 维护 | 推荐 |
|------|------|------|------|------|
| **本机 PostgreSQL** | <1ms | ¥0（服务器自带） | 需自己备份 | **推荐** |
| 阿里云 RDS PostgreSQL | ~2ms（同区域） | ~¥70/月起 | 自动备份、监控 | 预算充足时 |
| Supabase | 200-400ms（跨境） | 免费层可用 | 无需维护 | **不推荐国内部署** |

**结论**：数据库必须有（文章去重、存储、查询都依赖它），但直接装在服务器本机就行，不需要额外花钱。

---

## 钉钉集成架构

### 需要的钉钉开放平台能力

| 能力 | 钉钉 API | 用途 |
|------|----------|------|
| **机器人消息** | Stream 模式 / Webhook | 接收院长指令、推送每日简报 |
| **H5 微应用** | 企业内部应用 | 前端页面（政策看板、信源管理等） |
| **通讯录** | `/topapi/v2/user/list` | 获取部门人员信息 |
| **日程** | `/topapi/calendar/v2/` | 读取/创建日程提醒 |
| **知识库** | 钉钉文档 API | 访问内部文档和知识库 |
| **工作通知** | `asyncsend_v2` | 向指定用户推送消息 |

### 钉钉机器人工作流

```
院长在钉钉发消息
    │
    ▼
钉钉 Stream 长连接 ──→ FastAPI 接收
    │
    ▼
意图识别（LLM）
    │
    ├─ "今天有什么重要政策？" → 查 policy_intel feed → 返回摘要
    ├─ "科技部最近有什么人事变动？" → 查 personnel_intel → 返回结果
    ├─ "帮我关注这个政策" → 标记 importance → 加入日程提醒
    ├─ "发给张三看看" → 查通讯录 → 工作通知转发
    └─ "本周简报" → 聚合各维度数据 → 生成 Markdown 简报
```

### 钉钉 Stream 模式的优势

传统 Webhook 模式需要公网可达的回调 URL，而 **Stream 模式**：
- 机器人主动连接钉钉服务器（出站连接），不需要公网 IP 或域名
- 天然支持内网部署
- 断线自动重连
- 官方 Python SDK：`dingtalk-stream`

```python
# 示例：钉钉 Stream 机器人集成
pip install dingtalk-stream

# .env 中配置
DINGTALK_APP_KEY=your_app_key
DINGTALK_APP_SECRET=your_app_secret
```

---

## 信源分布

| 爬取方式 | 总数 | 启用 | 说明 |
|---------|------|------|------|
| **static**（httpx + BS4） | ~78 | ~70 | 占大头，纯 HTTP 请求，资源消耗极低 |
| **dynamic**（Playwright） | ~19 | ~8 | 实际启用的只有 8 个 |
| **rss**（feedparser） | 8 | 8 | 纯解析 XML，几乎无开销 |
| **自定义 Parser**（API 调用） | 7 | 7 | HTTP API 调用，轻量 |

**启用的 86 个源中，只有 ~8 个用 Playwright**，占不到 10%。

## 现有的资源控制机制

- **Playwright 并发上限 3 个浏览器上下文**（`app/crawlers/utils/playwright_pool.py`，`PLAYWRIGHT_MAX_CONTEXTS=3`）
- **全局最多 5 个爬虫并发**（`app/config.py`，`MAX_CONCURRENT_CRAWLS=5`）
- **每个源同一时刻只跑 1 个实例**（scheduler `max_instances=1`）
- **任务启动有 0-300 秒随机延迟**，避免峰值冲击

## 服务器配置建议

### 最低配置（能跑）

| 资源 | 规格 | 原因 |
|------|------|------|
| CPU | 2 核 | 5 并发爬虫 + API 服务 |
| 内存 | **2 GB** | 应用 ~500MB + Playwright ~500MB + 系统 ~1GB |
| 硬盘 | 20 GB | JSON 输出 + 日志 + Chromium 二进制 (~500MB) |
| 网络 | 不限，但需要公网出口 | 访问各信源网站 |

### 推荐配置（生产环境）

| 资源 | 规格 | 原因 |
|------|------|------|
| CPU | **4 核** | 每日 6:00 高峰有 ~50 个源同时触发 |
| 内存 | **4 GB** | 可以把 Playwright 并发提到 5-8，提升动态源效率 |
| 硬盘 | 50 GB | 3 个月的数据量 + 余量 |

### 不需要的

- **不需要 GPU** — 没有 ML 推理
- **不需要 Redis/消息队列** — APScheduler 内存调度足够当前规模
- **不需要多机部署** — 86 个源单机完全能承载

## 部署注意事项

### 1. Playwright 系统依赖（最容易踩坑）

Linux 服务器上 Chromium 依赖大量系统库，部署时需要执行：

```bash
playwright install chromium
playwright install-deps
```

`install-deps` 会安装 libnss3、libatk、libgbm 等十几个系统库。如果是 Docker 部署，建议基于 `mcr.microsoft.com/playwright/python` 官方镜像。

### 2. 数据库

**推荐本机安装 PostgreSQL**，不用 Supabase：

```bash
# Ubuntu/Debian
sudo apt install postgresql postgresql-contrib
sudo -u postgres createdb crawler
# .env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/crawler
```

### 3. 海外信源访问

部分信源（ArXiv、GitHub、HackerNews）在国内访问可能不稳定。解决方案：

| 方案 | 适用场景 |
|------|---------|
| 服务器自带国际带宽（阿里云香港/新加坡） | 最简单，但钉钉延迟稍高 |
| 国内服务器 + HTTP 代理 | `.env` 配置 `HTTP_PROXY`，爬虫走代理 |
| 禁用不稳定的海外源 | 最保守，先保证核心功能 |

**Twitter 源**：需要 `twitterapi.io` 付费 API key，且该 API 本身走 HTTP，不受墙限制。

### 4. 钉钉应用配置

1. 登录 [钉钉开放平台](https://open.dingtalk.com) → 创建企业内部应用
2. 开启「机器人」能力 → 选择 Stream 模式
3. 获取 `AppKey` 和 `AppSecret` → 写入 `.env`
4. 配置 H5 微应用首页地址 → 指向服务器上的前端页面
5. 申请所需权限：通讯录只读、日程读写、工作通知等

## 调度频率概览

| 频率 | 源数量 | 示例 |
|------|--------|------|
| 每 2 小时 | ~5 | jiqizhixin_rss, hacker_news, github_trending |
| 每 4 小时 | ~12-15 | gov_cn_zhengce, beijing_zhengce, twitter 系列 |
| 每日 6:00 UTC | ~50+ | 大部分信源默认频率 |
| 每周一 3:00 UTC | ~5 | semantic_scholar, talent 系列 |
| 每月 1 日 2:00 UTC | ~5 | nature_index, csrankings |

## 扩容建议（源数量 > 150 时考虑）

1. **提高 `PLAYWRIGHT_MAX_CONTEXTS`** 从 3 到 5-10（需要内存 > 4GB）
2. **提高 `MAX_CONCURRENT_CRAWLS`** 从 5 到 10（需要 CPU > 4 核）
3. **引入 Redis 缓存层**（API 响应缓存、去重加速）
4. **切换分布式调度**（Celery + RabbitMQ 替代 APScheduler）

## 成本估算

| 项目 | 方案 | 月费 |
|------|------|------|
| 云服务器 | 阿里云 ECS 2核4G（国内） | ~¥100-150 |
| 数据库 | 本机 PostgreSQL | ¥0 |
| LLM API | DeepSeek（按量） | ~¥10-30（日均 ~1000 次调用） |
| 钉钉开放平台 | 企业内部应用 | ¥0 |
| 域名（可选） | 备案域名 | ~¥50/年 |
| **合计** | | **~¥120-200/月** |

之前方案（Vercel + Render + Supabase + OpenRouter）虽然初期免费，但国内无法直接访问，无法做钉钉应用。

---

## 部署步骤清单

**Phase 1: 基础设施**

- 购买阿里云/腾讯云 ECS（2核4G，Ubuntu 22.04）
- 安装 PostgreSQL、Python 3.11、Playwright 依赖
- 配置 `.env`（DATABASE_URL、LLM API Key）
- 部署爬虫 + API 服务（systemd 或 Docker）
- 验证：API 可访问、爬虫正常运行

**Phase 2: 钉钉集成**

- 创建钉钉企业内部应用
- 实现 Stream 模式机器人（接收消息 + 路由到 API）
- 实现每日简报推送（工作通知 API）
- 配置 H5 微应用（前端部署到同一服务器）
- 验证：钉钉内可正常使用

**Phase 3: 高级功能（按需）**

- 通讯录集成（查人、转发）
- 日程集成（政策截止日提醒）
- 知识库对接（RAG 问答）
- 权限管理（不同角色看到不同数据）
