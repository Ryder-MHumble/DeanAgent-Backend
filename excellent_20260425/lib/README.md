# SPA 爬虫方案 - Playwright

## 概述

本方案使用 **Playwright** 处理需要 JavaScript 渲染的网页爬取需求，适用于：
- 天池平台 (tianchi.aliyun.com)
- 华为竞赛平台 (competition.huaweicloud.com)
- 其他 SPA (Single Page Application) 网站

## 环境配置

### 1. 安装依赖

```bash
# 创建 Python 虚拟环境
uv venv /tmp/playwright-env --python 3.12
source /tmp/playwright-env/bin/activate

# 安装 Playwright
uv pip install playwright

# 安装浏览器和系统依赖
playwright install chromium
playwright install-deps chromium
```

### 2. 文件结构

```
/data/dataset/excellent_20260425/
├── lib/
│   ├── spa_crawler.py      # 通用 SPA 爬虫模块
│   └── README.md           # 本文档
├── ai_competitions/
│   ├── crawler_tianchi.py  # 天池爬虫
│   ├── crawler_huawei.py   # 华为竞赛爬虫
│   ├── tianchi_data/       # 天池爬取结果
│   │   ├── results.json
│   │   └── *.png           # 截图
│   └── huawei_data/        # 华为爬取结果
```

## 使用方法

### 基础用法

```bash
# 激活环境
source /tmp/playwright-env/bin/activate

# 爬取天池
python3 /data/dataset/excellent_20260425/ai_competitions/crawler_tianchi.py

# 爬取华为竞赛
python3 /data/dataset/excellent_20260425/ai_competitions/crawler_huawei.py
```

### 命令行工具

```bash
# 爬取任意 URL
python3 /data/dataset/excellent_20260425/lib/spa_crawler.py \
    --url "https://example.com" \
    --output result.json \
    --wait-for ".content" \
    --screenshot
```

### Python API

```python
import asyncio
import sys
sys.path.insert(0, "/data/dataset/excellent_20260425/lib")
from spa_crawler import SPACrawler

async def main():
    crawler = SPACrawler(headless=True)
    await crawler.start()
    
    result = await crawler.crawl(
        url="https://tianchi.aliyun.com/competition",
        wait_time=3000,
        screenshot=True,
    )
    
    # 保存登录态（如果需要）
    await crawler.save_state()
    await crawler.close()
    
asyncio.run(main())
```

## 功能特性

| 功能 | 说明 |
|------|------|
| **JS 渲染** | 完整支持 JavaScript 渲染 |
| **智能等待** | 自动等待网络空闲 + 可配置等待时间 |
| **JSON 提取** | 自动提取 Next.js/Nuxt.js/Vue 数据 |
| **截图** | 支持全页面截图 |
| **登录态持久化** | 保存 cookies/localStorage |
| **分页爬取** | 支持列表页自动翻页 |

## 已配置的凭证

| 平台 | 凭证位置 | 用途 |
|------|----------|------|
| Kaggle | `~/.kaggle/kaggle.json` | Kaggle API |
| 阿里云 | `~/.aliyun/credentials` | OSS 等云服务 |
| 华为云 | `~/.huaweicloud/credentials` | OBS 等云服务 |

## 注意事项

1. **反爬机制**：部分网站有反爬虫保护，建议：
   - 添加随机延时
   - 使用代理 IP
   - 模拟真实浏览器行为

2. **登录态**：需要登录的网站，首次运行后手动登录，然后调用 `save_state()` 保存状态

3. **资源消耗**：Playwright 会启动浏览器，内存占用约 200-500MB

## 输出示例

天池爬取已生成：
- `tianchi_list.png` - 竞赛列表页截图 (1.7MB)
- `competition_*.png` - 各竞赛排行榜截图
- `results.json` - 结构化数据
