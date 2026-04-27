# 国内程序设计竞赛获奖信息爬虫

## 概述

本爬虫用于抓取国内主要程序设计竞赛的获奖者信息，包括：

- **NOI/NOIP** - 全国青少年信息学奥林匹克竞赛
- **ICPC** - 国际大学生程序设计竞赛
- **CCPC** - 中国大学生程序设计竞赛
- **蓝桥杯** - 全国软件和信息技术专业人才大赛
- **GPLT** - 团体程序设计天梯赛
- **CCF CSP** - 计算机软件能力认证
- **百度之星** - 程序设计大赛
- **CUMCM** - 全国大学生数学建模竞赛

## 文件说明

```
olympiad/
├── crawler.py      # 爬虫脚本
├── results.json    # 爬取结果 (JSON格式)
└── README.md       # 本说明文档
```

## 使用方法

### 运行爬虫

```bash
python3 crawler.py
```

### 依赖

```bash
pip install requests beautifulsoup4 lxml
# 或在 Ubuntu 上:
sudo apt-get install python3-requests python3-bs4 python3-lxml
```

## 输出格式

### results.json 结构

```json
{
  "source": "olympiad",
  "crawl_time": "2026-04-25T06:47:16.123456Z",
  "total_competitions": 9,
  "total_awardees": 131,
  "competitions": [
    {
      "name": "竞赛名称",
      "year": 2024,
      "awardees": [
        {
          "name": "获奖者姓名/团队名",
          "school": "所属学校",
          "award": "奖项等级",
          "rank": "排名"
        }
      ],
      "source_url": "数据来源网址",
      "crawl_status": "爬取状态",
      "note": "备注说明"
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 获奖者姓名或团队名称 |
| `school` | string | 所属学校/单位 |
| `award` | string | 奖项等级（如：金牌、一等奖等） |
| `rank` | string | 排名或范围（如：1-10, Top 10%） |

## 爬取策略

### 1. NOI/NOIP (noi.cn)

- **方法**: 请求官网新闻页面，解析获奖公告链接
- **挑战**: 网站使用部分 JavaScript 渲染
- **处理**: 解析页面链接，提取有价值的新闻标题和链接

### 2. ICPC (icpc.global)

- **方法**: 访问国际官网获取全球总决赛和区域赛结果
- **挑战**: 国际站点，部分内容需 JavaScript
- **处理**: 提取静态 HTML 中的比赛结果

### 3. CCPC (ccpc.io)

- **方法**: 访问中国程序设计竞赛官网
- **挑战**: 网站可能为动态渲染
- **处理**: 提取可用的静态内容

### 4. 蓝桥杯 (lanqiao.cn)

- **方法**: 访问蓝桥云课官网
- **挑战**: 获奖名单可能需要登录或在不同页面
- **处理**: 结合已知信息补充典型获奖情况

## 注意事项

### 遵守 robots.txt

爬虫会遵守各网站的 robots.txt 规则：
- 请求间隔设置为 1 秒，避免对服务器造成压力
- 使用合理的 User-Agent 标识

### 数据时效性

- 获奖名单通常在每年赛后公布
- 建议定期重新爬取获取最新数据
- 部分历史数据可能需要手动补充

### 反爬措施

如遇到访问限制：
1. 增加请求延时（修改 `delay` 参数）
2. 使用代理 IP 轮换
3. 对于重度 JavaScript 渲染的页面，考虑使用 Selenium/Playwright

## 扩展建议

### 使用 Selenium 处理动态页面

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument('--headless')
driver = webdriver.Chrome(options=options)
driver.get('https://www.noi.cn/xw/')
# 等待页面加载并解析
```

### 添加更多竞赛

可在 `OtherCompetitionCrawler` 类中添加：
- 华为软件精英挑战赛
- 阿里云天池大赛
- 腾讯广告算法大赛
- Kaggel 竞赛中国区获奖者

## 更新日志

- **2026-04-25**: 初始版本，支持 NOI/ICPC/CCPC/蓝桥杯等主要竞赛

## 许可

本爬虫仅供学习研究使用，请遵守相关法律法规和网站使用条款。
