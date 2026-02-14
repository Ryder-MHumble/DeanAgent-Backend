# 业务 API 设计文档 (v2)

> 本文档定义 Information_Crawler 后端为 Dean-Agent 前端提供的业务级 API 接口。
> v2 API 基于 data/raw/ JSON 文件提供业务数据，与 v1（数据库 CRUD）并行运行。

---

## 一、架构概览

```
data/raw/ JSON ──→ json_reader.py ──→ business/*_service.py ──→ api/v2/*.py ──→ 前端
                                           │
                                    llm_service.py (OpenRouter)
                                    (可选增强: aiInsight, matchScore)
```

- **数据源**: `data/raw/{dimension}/{group}/{source_id}/{YYYY-MM-DD}.json`
- **LLM**: OpenRouter API，通过 `?enhanced=true` 参数触发
- **v1 API 不受影响**: 原有 `/api/v1/` 端点继续工作

---

## 二、API 端点总览

| 模块 | 端点 | 方法 | 需要 LLM | 数据状态 |
|------|------|------|---------|---------|
| **政策情报** | `/api/v2/policy/national` | GET | 可选 | ✅ 17 条 |
| | `/api/v2/policy/beijing` | GET | 可选 | ✅ 26 条 |
| **科技前沿** | `/api/v2/tech/industry-news` | GET | 否 | ✅ 33 条 |
| | `/api/v2/tech/trends` | GET | 是 | ✅ 需LLM |
| | `/api/v2/tech/hot-topics` | GET | 可选 | ✅ 社区数据 |
| **高校生态** | `/api/v2/university/peers` | GET | 否 | ✅ 11 机构 |
| | `/api/v2/university/personnel` | GET | 否 | ✅ 19 条 |
| | `/api/v2/university/research` | GET | 否 | ✅ 奖项数据 |
| **人才雷达** | `/api/v2/talent/index` | GET | 否 | ✅ 32 条 |
| **活动日程** | `/api/v2/events/recommended` | GET | 否 | ✅ 212 条 |
| **院长早报** | `/api/v2/briefing/metrics` | GET | 否 | ✅ 7 维度 |
| | `/api/v2/briefing/priorities` | GET | 否 | ✅ 规则打分 |
| | `/api/v2/briefing/daily` | GET | 是 | ✅ 需LLM |

---

## 三、各端点详细定义

### 3.1 政策情报 `/api/v2/policy/`

#### GET /national
国家政策列表。

**参数**: `date_from`, `date_to` (date), `limit` (int, default 50), `enhanced` (bool, default false)

**响应**: `PolicyListResponse`
```json
{
  "items": [{
    "id": "abc123def456",
    "title": "关于加快招标投标领域人工智能推广应用的实施意见",
    "url": "https://...",
    "agency": "国家发展改革委",
    "agency_type": "national",
    "match_score": 0,
    "status": "active",
    "published_at": "2026-02-13T00:00:00",
    "source_id": "ndrc_policy",
    "source_name": "发改委-通知通告",
    "ai_insight": "",
    "detail": ""
  }],
  "total": 17,
  "dimension": "national_policy"
}
```

当 `enhanced=true` 时，LLM 会填充 `match_score` (0-100) 和 `ai_insight` 字段。

#### GET /beijing
同上，dimension 为 `beijing_policy`。

---

### 3.2 科技前沿 `/api/v2/tech/`

#### GET /industry-news
行业动态（自动分类）。

**参数**: `date_from`, `date_to`, `limit`

**响应**: `IndustryNewsResponse`
```json
{
  "items": [{
    "id": "...",
    "title": "...",
    "url": "...",
    "source": "钛媒体",
    "news_type": "投融资",
    "date": "2026-02-13",
    "impact": "较大",
    "summary": "",
    "ai_analysis": ""
  }],
  "total": 33
}
```

`news_type` 自动分类: 投融资 | 新产品 | 政策 | 收购 | 其他
`impact` 自动评级: 重大 | 较大 | 一般

#### GET /trends (需要 LLM)
技术趋势分析。LLM 从近期文章中提取趋势。

#### GET /hot-topics
社区热点话题。`enhanced=true` 启用 LLM 合并分析。

---

### 3.3 高校生态 `/api/v2/university/`

#### GET /peers
同行动态（按机构聚合）。返回 11 个机构的活跃度、最新动态、威胁等级。

#### GET /personnel
人事变动。关键词匹配：任命/院长/校长/书记/当选/院士。

#### GET /research
科研成果。基础分类：论文/专利/获奖。

---

### 3.4 人才雷达 `/api/v2/talent/`

#### GET /index
人才相关文章列表。

---

### 3.5 活动日程 `/api/v2/events/`

#### GET /recommended
会议/活动推荐。含 AI 领域分类。

---

### 3.6 院长早报 `/api/v2/briefing/`

#### GET /metrics
各维度指标卡片（文章数、源数、最新爬取时间）。

#### GET /priorities
优先事项（规则引擎打分排序：人事变动 > 政策 > 奖项）。

#### GET /daily (需要 LLM)
AI 每日简报生成。

---

## 四、前端对接说明

### 可直接对接的模块
| 前端模块 | v2 API | 说明 |
|---------|--------|------|
| 政策情报 → 国家政策 | `/api/v2/policy/national` | 直接映射 |
| 政策情报 → 北京政策 | `/api/v2/policy/beijing` | 直接映射 |
| 科技前沿 → 行业动态 | `/api/v2/tech/industry-news` | 直接映射 |
| 高校生态 → 同行动态 | `/api/v2/university/peers` | 聚合后映射 |
| 高校生态 → 人事变动 | `/api/v2/university/personnel` | 关键词过滤 |
| 高校生态 → 科研成果 | `/api/v2/university/research` | 基础分类 |
| 人才雷达 → 人才指数 | `/api/v2/talent/index` | 列表数据 |
| 活动日程 → 活动推荐 | `/api/v2/events/recommended` | 直接映射 |
| 院长早报 → 指标卡片 | `/api/v2/briefing/metrics` | 统计聚合 |
| 院长早报 → 优先事项 | `/api/v2/briefing/priorities` | 规则打分 |

### 需要 LLM 才能使用的模块
| 前端模块 | v2 API | 说明 |
|---------|--------|------|
| 科技前沿 → 技术趋势 | `/api/v2/tech/trends` | LLM 提取趋势 |
| 科技前沿 → 热点话题 | `/api/v2/tech/hot-topics?enhanced=true` | LLM 聚合话题 |
| 院长早报 → 每日简报 | `/api/v2/briefing/daily` | LLM 生成简报 |

### 暂不支持的模块（需补充信源或外部系统）
| 前端模块 | 原因 |
|---------|------|
| 政策情报 → 领导讲话 | 无领导讲话信源 |
| 政策情报 → 政策机会匹配 | 需 LLM 深度分析 |
| 人才雷达 → 回流追踪 | 需多信号检测 |
| 人才雷达 → 学术流动 | 需 LLM 提取 |
| 科技前沿 → KOL 追踪 | 需 Semantic Scholar 扩展 |
| 院内管理（全部） | 内部 OA 数据 |
| 人脉网络（全部） | CRM 数据 |
| 智能日程（全部） | 日历 API |

---

## 五、通用参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `date_from` | date (YYYY-MM-DD) | 起始日期过滤 |
| `date_to` | date (YYYY-MM-DD) | 截止日期过滤 |
| `limit` | int | 返回数量上限 |
| `enhanced` | bool | 启用 LLM 增强（仅部分端点） |

---

## 六、LLM 服务配置

```env
# .env
OPENROUTER_API_KEY=sk-or-v1-xxx
OPENROUTER_MODEL=google/gemini-2.0-flash-001
```

LLM 服务位于 `app/services/llm_service.py`，提供：
- `call_llm()` — 通用文本生成
- `call_llm_json()` — 结构化 JSON 输出

所有 LLM 调用可选（graceful degradation）：LLM 失败时返回基础数据。
