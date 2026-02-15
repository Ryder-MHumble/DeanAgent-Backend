# 服务器部署要求

> 最后更新: 2026-02-15

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

### 2. 数据库连接

使用 Supabase（远程 PostgreSQL），网络延迟比本地 DB 高。确保服务器和 Supabase 实例在同一区域（region）。

### 3. 目标网站封 IP

服务器 IP 是固定的，部分源可能限流或封禁机房 IP 段。本地开发用家用 IP 没问题，生产环境可能需要考虑代理。

### 4. Twitter 源需要 API Key

7 个 twitter 源依赖 `twitterapi.io`，需要付费 API key，在 `.env` 中配置 `TWITTER_BEARER_TOKEN`。

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

一台 **2 核 4G 云服务器**（阿里云 ECS / 腾讯云 CVM）约 100-150 元/月，足以满足当前 86 个启用源的生产需求。
