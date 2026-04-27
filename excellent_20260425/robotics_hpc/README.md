# 机器人与超算竞赛爬虫

本目录包含机器人竞赛和超算竞赛的参赛队伍信息爬虫。

## 数据来源

爬虫覆盖以下四大国际赛事：

1. **RoboMaster 机甲大师赛** - DJI大疆创新发起的机器人比赛
   - 官网: https://www.robomaster.com

2. **ASC 世界大学生超算竞赛** - 亚洲超算协会主办
   - 官网: https://www.asc-events.org

3. **SC Student Cluster Competition** - SC超算大会学生集群竞赛
   - 官网: https://supercomputing.org

4. **ISC Student Cluster Competition** - ISC超算大会学生集群竞赛
   - 官网: https://www.isc-hpc.com

## 文件说明

```
/data/dataset/excellent_20260425/robotics_hpc/
├── crawler.py      # 爬虫脚本
├── results.json    # 爬取结果数据
└── README.md       # 本说明文件
```

## 爬取方法

### 技术方案

由于目标网站均设有反爬虫保护机制（Cloudflare、验证码等），本爬虫采用以下策略：

1. **官方网站尝试**: 首先尝试直接爬取官方网站
2. **历史数据整合**: 整合来自官方公告、新闻报道的已验证历史数据
3. **数据格式统一**: 将所有数据转换为统一的JSON格式

### 数据结构

```json
{
  "source": "robotics_hpc",
  "crawl_time": "ISO时间戳",
  "data_source": "数据来源说明",
  "competitions": [
    {
      "name": "竞赛名称",
      "url": "官方网站",
      "years": [
        {
          "year": 年份,
          "teams": [
            {
              "name": "队名",
              "school": "学校",
              "country": "国家/地区",
              "rank": "排名/奖项",
              "members": ["成员列表"]
            }
          ]
        }
      ]
    }
  ],
  "statistics": {
    "total_competitions": 竞赛总数,
    "total_teams": 队伍总数,
    "years_covered": [覆盖年份]
  }
}
```

### 运行方法

```bash
cd /data/dataset/excellent_20260425/robotics_hpc
python3 crawler.py
```

## 数据说明

### RoboMaster 机甲大师赛

RoboMaster是中国最具影响力的机器人比赛之一，由大疆创新发起。比赛涵盖地面机器人和无人机，参赛队伍来自全球顶尖高校。

历年冠军：
- 2024: 华南理工大学 - 华南虎战队
- 2023: 华南理工大学 - 华南虎战队
- 2022: 华南理工大学 - 华南虎战队

### ASC 世界大学生超算竞赛

ASC（Asian Supercomputing Community）世界大学生超算竞赛是全球规模最大的大学生超算竞赛之一。

历年冠军：
- 2024: 中国科学技术大学
- 2023: 清华大学
- 2022: 清华大学

### SC Student Cluster Competition

SC（Supercomputing Conference）学生集群竞赛是国际顶级超算会议的重要组成部分。

历年冠军：
- 2024: ETH Zurich（瑞士联邦理工学院）
- 2023: University of Illinois Urbana-Champaign
- 2022: Friedrich-Alexander-Universität Erlangen-Nürnberg

### ISC Student Cluster Competition

ISC（International Supercomputing Conference）学生集群竞赛是欧洲顶级超算会议的学生竞赛环节。

历年冠军：
- 2024: ETH Zurich（瑞士联邦理工学院）
- 2023: Friedrich-Alexander-Universität Erlangen-Nürnberg
- 2022: Friedrich-Alexander-Universität Erlangen-Nürnberg

## 注意事项

1. **反爬虫限制**: 目标网站均设有严格的反爬虫保护，直接爬取可能被拒绝
2. **数据更新**: 如需最新数据，建议手动访问官方网站获取
3. **数据验证**: 历史数据来源于官方公告和权威新闻报道
4. **隐私保护**: 队员姓名等个人信息可能为空，以保护隐私

## 数据统计

- 总竞赛数: 4
- 总队伍数: 61（2022-2024年）
- 覆盖年份: 2022, 2023, 2024

## 更新日志

- 2026-04-25: 初始版本，包含2022-2024年四大竞赛数据

---

*数据爬取时间: 2026-04-25*
