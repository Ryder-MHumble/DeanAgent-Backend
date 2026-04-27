# CTFtime Crawler

抓取 CTFtime 战队排名和比赛信息的爬虫工具。

## 概述

本爬虫使用 CTFtime 官方 API 获取以下数据：

- **全球战队排名** - 当前年度排名前列的 CTF 战队
- **战队详细信息** - 国家、评分、别名等
- **比赛活动** - 近期和即将举行的 CTF 比赛
- **比赛结果** - 年度比赛成绩统计

## CTFtime API 端点

爬虫使用以下 API 端点：

| 端点 | 描述 |
|------|------|
| `/api/v1/top/` | 获取当前年度顶级战队排名 |
| `/api/v1/teams/{id}/` | 获取特定战队详细信息 |
| `/api/v1/events/` | 获取比赛活动列表 |
| `/api/v1/results/{year}/` | 获取年度比赛结果 |

官方 API 文档: https://ctftime.org/api/

## 安装依赖

```bash
pip install requests
```

## 使用方法

### 基本用法

```bash
python3 crawler.py
```

### 命令行参数

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `--teams` | 100 | 获取战队数量 |
| `--events` | 50 | 获取比赛数量 |
| `-o, --output` | results.json | 输出文件路径 |
| `-v, --verbose` | False | 显示详细输出 |

### 示例

```bash
# 获取前 50 名战队和 30 场比赛
python3 crawler.py --teams 50 --events 30 -o results.json -v

# 获取前 200 名战队
python3 crawler.py --teams 200 --events 100 -o full_results.json
```

## 输出格式

输出为 JSON 格式，结构如下：

```json
{
  "source": "ctftime",
  "crawl_time": "2026-04-25T06:45:49.640757Z",
  "crawl_config": {
    "teams_limit": 50,
    "events_limit": 30
  },
  "teams": [
    {
      "id": 1301,
      "name": "Team H4C",
      "country": "KR",
      "academic": false,
      "primary_alias": "TeamH4C",
      "aliases": ["TeamH4C", "C4C"],
      "rating": {
        "rating_place": 1,
        "organizer_points": 0,
        "rating_points": 832.119178952,
        "country_place": 1
      },
      "logo": "https://ctftime.org/media/...",
      "points": 832.1191789517452,
      "rank": 1
    }
  ],
  "events": [
    {
      "id": 3192,
      "title": "CTF@AC26 - Quals",
      "format": "Jeopardy",
      "start": "2026-04-25T07:00:00+00:00",
      "finish": "2026-04-26T07:00:00+00:00",
      "url": "https://ctf.ac.upt.ro/",
      "participants": 73,
      "weight": 24.53,
      "onsite": false,
      "location": ""
    }
  ],
  "results": {
    "events_count": 15,
    "events": ["2969", "2970", ...]
  },
  "summary": {
    "total_teams": 50,
    "total_events": 30,
    "countries_represented": 23
  }
}
```

## 数据字段说明

### 战队字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `id` | int | CTFtime 战队 ID |
| `name` | string | 战队名称 |
| `country` | string | 国家代码 (ISO 3166-1 alpha-2) |
| `academic` | bool | 是否为学术战队 |
| `primary_alias` | string | 主要别名 |
| `aliases` | array | 所有别名列表 |
| `rating` | object | 当前年度评分信息 |
| `logo` | string | 战队 Logo URL |
| `points` | float | 评分积分 |
| `rank` | int | 爬取时的排名 |

### 评分字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `rating_place` | int | 全球排名 |
| `rating_points` | float | 评分积分 |
| `country_place` | int | 国内排名 |
| `organizer_points` | float | 组织者积分 |

### 比赛字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `id` | int | 比赛 ID |
| `title` | string | 比赛名称 |
| `format` | string | 比赛形式 (Jeopardy, Attack-Defense 等) |
| `start` | string | 开始时间 (ISO 8601) |
| `finish` | string | 结束时间 (ISO 8601) |
| `url` | string | 比赛官网 |
| `participants` | int | 参赛队伍数 |
| `weight` | float | 权重因子 |
| `onsite` | bool | 是否线下赛 |
| `location` | string | 比赛地点 |

## 注意事项

1. **API 限制**: CTFtime API 没有明确的速率限制文档，但请合理使用
2. **请求间隔**: 爬虫默认在请求之间有 0.5 秒延迟
3. **成员信息**: API 不提供战队成员列表
4. **User-Agent**: 爬虫使用自定义 User-Agent 标识

## 文件结构

```
/data/dataset/excellent_20260425/ctftime/
├── crawler.py      # 爬虫脚本
├── results.json    # 爬取结果
└── README.md       # 本文档
```

## 许可

数据来源: CTFtime.org - 请尊重 CTFtime 的数据使用条款。

> This API is provided for data analysis and mobile applications only.
> You can not use this API to run CTFtime clones.
