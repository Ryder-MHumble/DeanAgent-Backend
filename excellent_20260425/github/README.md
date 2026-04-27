# GitHub AI 领域贡献者爬虫

抓取 LLM/AI Agents 相关热门仓库的主要贡献者信息。

## 爬取方法

### 数据来源

- **数据源**: GitHub REST API
- **搜索范围**: 以下 topic 的仓库
  - `llm` - 大语言模型
  - `machine-learning` - 机器学习
  - `deep-learning` - 深度学习
  - `nlp` - 自然语言处理
  - `reinforcement-learning` - 强化学习
  - `autonomous-agents` - 自主智能体

### 筛选条件

| 条件 | 值 | 说明 |
|------|-----|------|
| 最小 Stars | 1000 | 热门项目 |
| 推送时间 | > 2023-01-01 | 近期活跃项目 |
| 最小贡献数 | 50 | 主要贡献者 |
| 最大仓库数 | 30 | 控制爬取规模 |

### API 端点

1. **搜索仓库**: `GET /search/repositories`
   - 参数: `q=topic:{topic} stars:>1000 pushed:>2023-01-01`
   - 排序: `sort=stars&order=desc`

2. **获取贡献者**: `GET /repos/{owner}/{repo}/contributors`
   - 参数: `per_page=100`

## ⚠️ 重要：需要 GitHub Token

**未认证请求速率限制极低（60 次/小时），强烈建议配置 GitHub Token！**

### 配置方法

```bash
# 方法 1: 环境变量（推荐）
export GITHUB_TOKEN="your_github_token_here"
python3 crawler.py

# 方法 2: 直接设置
# 编辑 crawler.py，在脚本开头设置 GITHUB_TOKEN
```

### 获取 GitHub Token

1. 访问 https://github.com/settings/tokens
2. 点击 "Generate new token (classic)"
3. 勾选 `public_repo` 权限
4. 生成并复制 token

### 认证 vs 未认证对比

| 认证状态 | 速率限制 | 等待时间 | 推荐场景 |
|----------|----------|----------|----------|
| 未认证 | 60 次/小时 | 约 1 分钟/请求 | 不推荐 |
| 已认证 | 5000 次/小时 | 约 0.1 秒/请求 | 推荐 |

## 使用方法

### 完整爬虫（Python）

```bash
cd /data/dataset/excellent_20260425/github
export GITHUB_TOKEN="your_token"  # 重要！
python3 crawler.py
```

### 简化版（Bash）

```bash
cd /data/dataset/excellent_20260425/github
export GITHUB_TOKEN="your_token"
./crawler_simple.sh
```

## 输出格式

```json
{
  "source": "github",
  "crawl_time": "2026-04-25T06:45:00Z",
  "repositories": [
    {
      "full_name": "Significant-Gravitas/AutoGPT",
      "stars": 183741,
      "language": "Python",
      "topics": ["llm", "autonomous-agents"],
      "description": "项目描述",
      "contributors": [
        {
          "login": "username",
          "contributions": 150,
          "avatar_url": "https://avatars.githubusercontent.com/u/...",
          "html_url": "https://github.com/username"
        }
      ]
    }
  ],
  "stats": {
    "total_repos": 5,
    "total_contributors": 20,
    "topics_searched": ["llm", "machine-learning", ...]
  }
}
```

## 字段说明

### 仓库信息

| 字段 | 类型 | 说明 |
|------|------|------|
| full_name | string | 仓库全名 (owner/repo) |
| stars | number | Star 数量 |
| language | string | 主要编程语言 |
| topics | array | 主题标签 |
| description | string | 项目描述（前100字符） |

### 贡献者信息

| 字段 | 类型 | 说明 |
|------|------|------|
| login | string | 用户名 |
| contributions | number | 贡献次数 |
| avatar_url | string | 头像 URL |
| html_url | string | 主页 URL |

## 文件说明

```
/data/dataset/excellent_20260425/github/
├── crawler.py        # 完整爬虫脚本（Python）
├── crawler_simple.sh # 简化版爬虫（Bash）
├── results.json      # 爬取结果
└── README.md         # 本说明文档
```

## 爬取的热门仓库

当前包含的 AI 领域热门仓库：

1. **AutoGPT** (183k+ stars) - 自主 AI 代理
2. **LangChain** (102k+ stars) - LLM 应用框架
3. **Transformers** (135k+ stars) - HuggingFace 机器学习库
4. **Stable Diffusion** (72k+ stars) - 图像生成模型
5. **Stable Diffusion WebUI** (145k+ stars) - 图像生成界面

## 注意事项

1. **必须配置 GitHub Token** 才能完整运行
2. 脚本会自动处理速率限制并等待
3. 结果按 Stars 数降序排列
4. 贡献者按贡献数降序排列

---

**爬取时间**: 2026-04-25
**数据状态**: 示例数据（需 Token 获取完整数据）
