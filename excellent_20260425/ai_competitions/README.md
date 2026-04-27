# AI竞赛获奖信息爬虫

## 概述

本爬虫用于抓取国内主要AI竞赛平台的获奖团队信息，包括：
- CCF BDCI (DataFountain)
- 阿里天池
- KDD Cup
- 华为软件精英挑战赛

## 文件说明

```
/data/dataset/excellent_20260425/ai_competitions/
├── crawler.py       # 爬虫脚本
├── results.json     # 爬取结果（JSON格式）
└── README.md        # 本说明文档
```

## 环境依赖

```bash
pip install requests beautifulsoup4
```

## 使用方法

### 运行爬虫

```bash
python3 crawler.py
```

### 自定义配置

如果需要调整爬取参数，可以修改 `crawler.py` 中的以下配置：

1. **限制爬取数量**：修改各爬虫类中的 `[:5]` 或 `[:10]` 参数
2. **调整延迟时间**：修改 `delay()` 方法的参数
3. **修改输出路径**：修改 `output_path` 变量

## 爬取方法

### 1. DataFountain (CCF BDCI)

**爬取策略**：
- 访问竞赛列表页面：`https://www.datafountain.cn/competitions`
- 解析HTML获取竞赛链接
- 访问每个竞赛的详情页和排行榜页

**数据提取**：
- 竞赛名称：从 `<h1>` 或 `.title` 元素提取
- 排行榜：从排行榜表格 `<table>` 中解析团队信息

**注意事项**：
- 需要处理JavaScript渲染的内容
- 部分竞赛可能需要登录才能查看排行榜

### 2. 阿里天池

**爬取策略**：
- 优先尝试API接口：`https://tianchi.aliyun.com/competition/proxy/list`
- 如果API失败，则解析HTML页面
- 竞赛详情页：`https://tianchi.aliyun.com/competition/{id}`

**数据提取**：
- 通过API获取竞赛列表和排行榜
- 或从HTML中解析竞赛卡片和排行榜表格

**注意事项**：
- 天池使用动态加载，可能需要API认证
- 排行榜API：`/competition/entrance/{id}/rankList`

### 3. KDD Cup

**爬取策略**：
- 访问KDD Cup主页面：`https://www.kdd.org/kdd-cup`
- 解析历史竞赛列表
- 访问各年度竞赛页面

**数据提取**：
- 竞赛名称：从 `<h1>` 或 `<h2>` 元素提取
- 排行榜：从表格中解析团队排名

**注意事项**：
- KDD Cup为英文网站
- 不同年份的页面结构可能不同

### 4. 华为软件精英挑战赛

**爬取策略**：
- 访问华为云竞赛平台：`https://competition.huaweicloud.com`
- 解析竞赛列表
- 尝试API或HTML解析排行榜

**数据提取**：
- 竞赛名称：从 `<h1>` 或 `.competition-name` 提取
- 排行榜：尝试API `{url}/leaderboard` 或HTML表格

**注意事项**：
- 华为云平台可能需要登录
- 部分竞赛可能已结束，排行榜可能不可访问

## 反爬机制应对

### 1. 请求头伪装
```python
headers = {
    'User-Agent': 'Mozilla/5.0 ...',
    'Accept': 'text/html,application/xhtml+xml,...',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}
```

### 2. 延迟访问
- 每次请求后延迟 1-2 秒
- 避免频繁请求触发封禁

### 3. Session保持
- 使用 `requests.Session()` 保持会话状态
- 自动处理Cookie

### 4. 错误处理
- 捕获网络异常和解析错误
- 记录失败URL，便于后续重试

## 输出格式

### JSON 结构

```json
{
  "source": "ai_competitions",
  "crawl_time": "2026-04-25T06:45:00",
  "competitions": [
    {
      "name": "2024 CCF BDCI 大赛",
      "platform": "DataFountain",
      "year": 2024,
      "tracks": [
        {
          "track_name": "主赛道",
          "winners": [
            {
              "rank": 1,
              "team_name": "冠军团队",
              "members": ["张三", "李四"],
              "score": 0.95
            }
          ]
        }
      ]
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| source | string | 数据来源标识 |
| crawl_time | string | 爬取时间（ISO 8601格式） |
| competitions | array | 竞赛列表 |
| name | string | 竞赛名称 |
| platform | string | 竞赛平台 |
| year | number | 竞赛年份 |
| tracks | array | 赛道列表 |
| track_name | string | 赛道名称 |
| winners | array | 获奖团队列表 |
| rank | number | 排名 |
| team_name | string | 团队名称 |
| members | array | 团队成员列表 |
| score | number/string | 得分 |

## 已知限制

1. **登录要求**：部分平台需要登录才能查看完整排行榜
2. **动态内容**：JavaScript渲染的内容可能无法直接解析
3. **验证码**：高频访问可能触发验证码
4. **数据完整性**：成员信息可能需要额外爬取
5. **反爬策略**：各平台可能更新反爬机制

## 改进建议

1. **使用Selenium/Playwright**：处理JavaScript渲染的内容
2. **添加代理池**：避免IP被封
3. **OCR识别**：处理验证码
4. **增量爬取**：记录已爬取的竞赛，避免重复
5. **数据验证**：添加数据完整性检查

## 许可声明

本爬虫仅供学术研究使用，请遵守各平台的服务条款和robots.txt规定。使用前请确认：
- 遵守网站的使用条款
- 不进行恶意爬取
- 合理设置爬取频率
- 尊重数据版权

## 更新日志

- **2026-04-25**: 初始版本，支持四大AI竞赛平台爬取

## 阿里云凭证配置

阿里云 AccessKey 已保存到 `~/.aliyun/credentials`：

```
access_key_id: <YOUR_ALIBABA_CLOUD_ACCESS_KEY_ID>
access_key_secret: <YOUR_ALIBABA_CLOUD_ACCESS_KEY_SECRET>
```

**注意**：阿里云凭证主要用于阿里云云服务（OSS、ECS 等），天池竞赛数据目前需要通过网页爬取获取。

如需使用阿里云 OSS 存储爬取结果：
```python
import oss2
auth = oss2.Auth('<YOUR_ALIBABA_CLOUD_ACCESS_KEY_ID>', '<YOUR_ALIBABA_CLOUD_ACCESS_KEY_SECRET>')
bucket = oss2.Bucket(auth, 'your-endpoint', 'your-bucket')
```

## 华为云凭证配置

华为云 AccessKey 已保存到 `~/.huaweicloud/credentials`：

```
access_key_id: HPUANVAPYN8KTSWK1GBB
secret_access_key: CpaHD1bdlXzGcKCdcZT959JWXuUBITAC9dt3vQTl
region: cn-north-4
Owner ID: 019dc3a464f57924a16ea3b2181867d5
```

**注意**：
- 华为云 AK/SK 主要用于华为云服务（OBS、ECS、IAM 等）
- 华为软件精英挑战赛平台 (`competition.huaweicloud.com`) 是 SPA 应用，无公开 API
- 竞赛数据需通过网页爬取（需处理 JavaScript 渲染）

**可用场景**：
- 华为云 OBS 存储（存储爬取结果）
- 华为云其他云服务 API
