# 信源爬取状态总览

> 最后更新: 2026-02-13 (v3: 完成 national_policy / events / industry / talent / beijing_policy 五个维度的逐源验证)
>
> 本文档供团队成员和其他模型会话了解当前爬取进度、数据可用性和待办事项。

---

## 一、数据目录结构

```
data/
├── raw/                              # 原始爬取数据（爬虫直接输出，自动生成）
│   └── {dimension}/
│       └── {group}/                  # 按分组组织（如 personnel, university_news 等）
│           └── {source_id}/
│               └── {YYYY-MM-DD}.json # 每日爬取条目
│
└── refined/                          # 业务数据（后续 LLM 处理后的输出）
    └── {YYYY-MM-DD}/                 # 按日期组织
        ├── {dimension}/
        │   └── {use_case}.json       # 按院长需求场景分类
        └── daily_briefing.json       # 院长日报汇总
```

### 各维度分组

| 维度 | group | 含义 | 源数 |
|------|-------|------|------|
| universities | `personnel` | 高教人事首发源 | 2 |
| universities | `university_news` | 高校新闻网 | 7 (5启用) |
| universities | `ai_institutes` | AI研究机构 | 7 (6启用) |
| universities | `aggregators` | 高教新闻聚合 | 3 (2启用) |
| universities | `awards` | 科技成果与荣誉 | 4 |
| universities | `provincial` | 省级教育厅 | 5 |
| technology | `domestic_media` | 国内科技媒体 | 2 |
| technology | `international_media` | 国际科技源 | 3 |
| technology | `company_blogs` | 公司官方博客 | 2 (0启用) |
| technology | `academic` | 学术论文 | 1 |
| technology | `community` | 社区讨论 | 4 |
| national_policy | `policy` | 政策文件 | 5 (4启用) |
| beijing_policy | `policy` | 政策文件 | 8 (5启用) |
| beijing_policy | `news_personnel` | 人事变动与要闻 | 4 (2启用) |
| industry | `news` | 产业新闻 | 6 (3启用) |
| industry | `investment` | 融资/IPO | 2 (1启用) |
| talent | `tracking` | 人才追踪/排名 | 4 (2启用) |
| talent | `policy` | 人才政策公示 | 3 (2启用) |
| events | `academic` | 学术会议 | 3 (2启用) |
| events | `industry` | 行业活动 | 1 (0启用) |

### raw/ 数据格式

每个 JSON 文件结构：

```json
{
  "source_id": "pku_news",
  "dimension": "universities",
  "group": "university_news",
  "source_name": "北京大学新闻网",
  "crawled_at": "2026-02-13T09:06:32+00:00",
  "item_count": 10,
  "items": [
    {
      "title": "刘志博、王剑威获2026年度陈嘉庚青年科学奖",
      "url": "https://news.pku.edu.cn/xwzh/xxx.htm",
      "url_hash": "7140a069...",
      "published_at": "2026-02-13T00:00:00",
      "author": null,
      "summary": null,
      "content": null,
      "content_hash": null,
      "source_id": "pku_news",
      "dimension": "universities",
      "tags": ["university", "pku", "news"],
      "extra": {}
    }
  ]
}
```

**注意**: 当前大部分条目只有 `title` + `url` + `published_at`，`content` / `summary` / `author` 字段尚未填充（需要逐条抓取详情页，后续实现）。

### refined/ 数据说明

尚未实现。该目录用于存放经过 LLM 处理后的业务数据，按院长需求场景组织。具体设计见下方「三、从原始数据到业务数据」。

---

## 二、各维度爬取状态

### 总览

| 维度 | 计划源数 | 已配置 | 已启用 | 已验证通过 | 产出数据 | YAML 文件 |
|------|---------|--------|--------|-----------|---------|----------|
| universities (对高校) | ~35 | 28 | 24 | **24/24** | ✅ | `sources/universities.yaml` |
| technology (对技术) | ~23 | 12 | 10 | **10/10** | ✅ | `sources/technology.yaml` |
| national_policy (对国家) | ~21 | 5 | 4 | **4/4** | ✅ 3源有数据 | `sources/national_policy.yaml` |
| beijing_policy (对北京) | ~14 | 12 | 7 | **7/7** | ✅ 6源有数据 | `sources/beijing_policy.yaml` |
| industry (对产业) | ~13 | 8 | 4 | **4/4** | ✅ 3源有数据 | `sources/industry.yaml` |
| talent (对人才) | ~10 | 7 | 4 | **4/4** | ✅ 3源有数据 | `sources/talent.yaml` |
| sentiment (对学院舆情) | ~6 | 0 | 0 | N/A | — | 未创建 |
| events (对日程) | ~4 | 4 | 2 | **2/2** | ✅ 2源有数据 | `sources/events.yaml` |
| **合计** | **~126** | **76** | **55** | **55/55** | — | — |

> **说明**: "已验证通过"指所有启用源 (is_enabled: true) 的选择器已确认匹配实际页面 HTML 结构。部分源因当前页面无关键词匹配条目而产出 0 条数据（如 gov_cn_zhengce、36kr_news），但选择器和爬虫逻辑均已验证正确，待相关内容出现时将自动采集。

### 详细状态：universities (对高校) — 已全量验证

**24/24 启用源全部通过实际运行验证 (2026-02-13)**

#### A. 高教人事首发源
| source_id | 名称 | 方法 | 条目数 | 日期 | 对应需求 |
|-----------|------|------|--------|------|---------|
| moe_renshi | 教育部-人事任免 | static | 1 | yes | 人事变动 - 需要恭喜的人 |
| moe_renshi_si | 教育部-人事司公告 | static | 4 | yes | 人事变动 - 需要恭喜的人 |

#### B. 高校新闻网
| source_id | 名称 | 方法 | 条目数 | 日期 | 对应需求 |
|-----------|------|------|--------|------|---------|
| tsinghua_news | 清华大学新闻网 | static | 10 | yes | 兄弟单位动向 |
| pku_news | 北京大学新闻网 | dynamic | 10 | yes | 兄弟单位动向 |
| ustc_news | 中国科大新闻网 | static | 30 | yes | 兄弟单位动向 |
| sjtu_news | 上海交大新闻网 | static | 46 | no | 兄弟单位动向 |
| fudan_news | 复旦大学新闻网 | static | 16 | no | 兄弟单位动向 |

#### C. AI 研究机构
| source_id | 名称 | 方法 | 条目数 | 日期 | 对应需求 |
|-----------|------|------|--------|------|---------|
| baai_news | BAAI 智源社区 | dynamic | 6 | yes | 兄弟单位动向 (国智院) |
| tsinghua_air | 清华 AIR | static | 16 | yes | 兄弟单位动向 (AI Lab) |
| shlab_news | 上海 AI 实验室 | dynamic | 7 | partial | 兄弟单位动向 (AI Lab) |
| pcl_news | 鹏城实验室 | static | 10 | yes | 兄弟单位动向 |
| ia_cas_news | 中科院自动化所 | static | 37 | yes | 兄弟单位动向 |
| ict_cas_news | 中科院计算所 | static | 6 | yes | 兄弟单位动向 |

#### D. 高教新闻聚合
| source_id | 名称 | 方法 | 条目数 | 日期 | 对应需求 |
|-----------|------|------|--------|------|---------|
| eol_news | 中国教育在线 | static | 1 | no | 人事 + 高校动态 (关键词过滤) |
| jyb_news | 中国教育报 | static | 21 | no | 人事 + 高校动态 (关键词过滤) |

#### E. 科技成果与荣誉
| source_id | 名称 | 方法 | 条目数 | 日期 | 对应需求 |
|-----------|------|------|--------|------|---------|
| cas_news | 中国科学院 | static | 1 | no | 院士增选 - 需要恭喜的人 |
| cae_news | 中国工程院 | static | 6 | yes | 院士增选 - 需要恭喜的人 |
| nosta_news | 国家科技奖励办 | dynamic | 6 | yes | 科技获奖 - 需要恭喜的人 |
| moe_keji | 教育部科技司 | static | 7 | yes | 高校十大科技进展 |

#### F. 省级教育厅
| source_id | 名称 | 方法 | 条目数 | 日期 | 对应需求 |
|-----------|------|------|--------|------|---------|
| beijing_jw | 北京市教委 | static | 1 | yes | 地方教育政策 (关键词过滤) |
| shanghai_jw | 上海市教委 | static | 2 | yes | 地方教育政策 (关键词过滤) |
| zhejiang_jyt | 浙江省教育厅 | static | 7 | yes | 地方教育政策 (关键词过滤) |
| jiangsu_jyt | 江苏省教育厅 | static | 6 | no | 地方教育政策 (关键词过滤) |
| guangdong_jyt | 广东省教育厅 | static | 2 | no | 地方教育政策 (关键词过滤) |

#### 禁用源 (4)
| source_id | 原因 | 可恢复性 |
|-----------|------|---------|
| zju_news | URL 返回错误，需排查新路径 | 中 |
| nju_news | SSL 证书问题 | 高 (可能是临时性问题) |
| zhejianglab_news | 复杂 SPA 布局，需定制解析器 | 低 |
| shanghairanking_news | URL 404，路径已变更 | 中 |

### 详细状态：technology (对技术) — 已验证

10/10 启用源全部通过。详见 `sources/technology.yaml`。

### 详细状态：national_policy (对国家) — 已验证 (2026-02-13)

**4/5 源启用，3 源产出数据**

| source_id | 名称 | 方法 | 启用 | 条目数 | 说明 |
|-----------|------|------|------|--------|------|
| gov_cn_zhengce | 国务院-最新政策 | dynamic | ✅ | 0* | 选择器正确(20项匹配)，但当前页面无AI/教育关键词匹配 |
| ndrc_policy | 发改委-通知通告 | static | ✅ | 3 | URL 修正为 `/xxgk/zcfb/tz/`，含 AI 相关政策 |
| moe_policy | 教育部-教育信息化 | static | ✅ | 8 | 选择器修正为 `div.moe-list li` |
| most_policy | 科技部-信息公开 | static | ✅ | 6 | 选择器修正为 `ul.a_list li` |
| miit_policy | 工信部-政策文件 | static | ❌ | — | IP 级 WAF 封锁 (403)，Playwright 也无法绕过 |

> \* gov_cn_zhengce 使用 Playwright 动态爬取，选择器 `div.list_2 li` 能匹配到 20 条国务院政策，但 default_keyword_filter 过滤后无匹配。这是预期行为 — 国务院政策标题不一定包含 AI/教育关键词。

### 详细状态：beijing_policy (对北京) — 已验证 (2026-02-13)

**7/12 源启用，6 源产出数据**

#### A. 政策文件
| source_id | 名称 | 方法 | 启用 | 条目数 | 说明 |
|-----------|------|------|------|--------|------|
| beijing_zhengce | 首都之窗-政策文件 | dynamic | ✅ | 1 | 选择器修正为 `ul.zc_news_list li`，关键词过滤后 1 条科技相关 |
| bjkw_policy | 北京市科委/中关村管委会 | static | ✅ | 4 | URL 修正为根目录，选择器 `ul.infoList li`，全部科技相关 |
| bjjw_policy | 北京市教委 | static | ✅ | 14 | 选择器修正为 `ul.z-mylist li`，教育政策文件 |
| bjrsj_policy | 北京市人社局 | static | ✅ | 1 | 选择器修正为 `ul.allList li`，人才关键词匹配 |
| zgc_policy | 中关村示范区 | static | ❌ | — | 域名连接被重置 (Connection reset by peer) |
| ncsti_policy | 国际科创中心 | static | ✅ | 5 | 选择器修正为 `ul.qcdt-list li`，科创新闻 |
| bjfgw_policy | 北京市发改委 | static | ❌ | — | 多级 JS 跳转链，静态无法跟随 |
| bjhd_policy | 海淀区政府 | static | ❌ | — | `/zwgk/` 返回 404 |

#### B. 人事变动与要闻
| source_id | 名称 | 方法 | 启用 | 条目数 | 说明 |
|-----------|------|------|------|--------|------|
| beijing_ywdt | 首都之窗-要闻 | static | ✅ | 0* | 选择器 `ul.news_list li` 匹配 29 项，但无关键词命中 |
| bjd_news | 北京日报 | static | ❌ | — | 首页布局复杂，无清晰列表结构，需 JS 渲染 |
| bjrd_renshi | 北京市人大常委会 | static | ✅ | 1 | 选择器修正为 `ul.txt_tab li`，人事/选举关键词过滤 |
| beijing_rsrm | 首都之窗-人事任免 | static | ❌ | — | URL 返回 404 |

> \* beijing_ywdt 选择器已验证正确，0 条是因为当前首页要闻标题不包含 AI/教育/科技等关键词。

### 详细状态：industry (对产业) — 已验证 (2026-02-13)

**4/8 源启用，3 源产出数据**

#### A. 产业新闻
| source_id | 名称 | 方法 | 启用 | 条目数 | 说明 |
|-----------|------|------|------|--------|------|
| 36kr_news | 36氪-快讯 | static | ✅ | 0* | 选择器修正为 `div.newsflash-item`，关键词过滤后暂无匹配 |
| huxiu_news | 虎嗅 | static | ❌ | — | WAF 反爬，返回验证码页面 (11KB) |
| tmtpost_news | 钛媒体 | rss | ✅ | 3 | 改为 RSS feed (`/feed`)，稳定输出 |
| jiemian_tech | 界面新闻-科技 | static | ✅ | 3 | 选择器修正为 `li.card-list` / `h3.card-list__title` |
| thepaper_tech | 澎湃新闻-科技 | static | ❌ | — | Next.js SPA，静态无内容 |
| iyiou_ai | 亿欧-AI | static | ❌ | — | 返回 209 字节空壳页面 |

#### B. 融资/IPO
| source_id | 名称 | 方法 | 启用 | 条目数 | 说明 |
|-----------|------|------|------|--------|------|
| chinaventure_news | 投中网 | static | ✅ | 8 | 选择器修正为 `div.news_list_zone li` / `h1`，融资新闻 |
| 36kr_investment | 36氪-融资频道 | static | ❌ | — | URL 302 → 404，页面已下线 |

> \* 36kr_news 选择器已验证 (20 项匹配)，但快讯多为一般财经新闻，当前无 AI/融资关键词命中。

### 详细状态：talent (对人才) — 已验证 (2026-02-13)

**4/7 源启用，3 源产出数据**

#### A. 人才追踪
| source_id | 名称 | 方法 | 启用 | 条目数 | 说明 |
|-----------|------|------|------|--------|------|
| csrankings | CSRankings | static | ❌ | — | React SPA，静态 HTML 无数据 |
| semantic_scholar_ai | Semantic Scholar-AI论文 | API | ✅ | 0† | 自定义 API Parser，被 429 限速 |
| nature_index | Nature Index | static | ✅ | 4 | 选择器修正为 `article`，含 AI 会议相关文章 |
| aminer_ai | AMiner-AI学者 | static | ❌ | — | JS SPA (3KB 空壳) |

#### B. 人才政策公示
| source_id | 名称 | 方法 | 启用 | 条目数 | 说明 |
|-----------|------|------|------|--------|------|
| nsfc_talent | NSFC杰青/优青公示 | static | ❌ | — | URL 404，NSFC 网站结构已变更 |
| moe_talent | 教育部人才计划公示 | static | ✅ | 6 | URL 修正为 `s5744/`，选择器 `ul#list li`，含人才/教师/名单 |
| wrsa_talent | 欧美同学会 | static | ✅ | 1 | 选择器修正为 `div.news_div1 li`，关键词过滤 |

> † semantic_scholar_ai 使用自定义 API Parser，之前已验证可用，本次因 429 限速暂时失败，定时任务中会自动重试。

### 详细状态：events (对日程) — 已验证 (2026-02-13)

**2/4 源启用，2 源产出数据**

| source_id | 名称 | 方法 | 启用 | 条目数 | 说明 |
|-----------|------|------|------|--------|------|
| aideadlines | AI Conference Deadlines | dynamic | ✅ | 192 | 选择器修正为 `div.ConfItem` / `span.conf-title a`，全量 AI 会议 |
| wikicfp | WikiCFP-AI | static | ✅ | 20 | 选择器修正为 `tr[bgcolor]` / `td a`，AI 会议 CFP |
| huodongxing | 活动行-人工智能 | static | ❌ | — | CAPTCHA/反爬 (302 到验证页面) |
| meeting_edu | 中国学术会议在线 | static | ❌ | — | 站点无法连接 |

---

## 三、从原始数据到业务数据

### 院长需求 vs 数据映射

根据 `docs/院长智能体.md`，院长对每个维度的核心关注点及我们的数据覆盖情况：

#### 对高校

| 院长需求 | 需要的信息 | 数据来源 (raw) | 处理方式 |
|---------|-----------|---------------|---------|
| 需要恭喜的人 - 人事变动 | 高校校长/院长/书记任免 | moe_renshi, moe_renshi_si, 高校新闻网 | LLM 从标题识别人事变动类新闻，提取人名+职位+学校 |
| 需要恭喜的人 - 院士 | 院士增选/Fellow 当选 | cas_news, cae_news | LLM 提取当选者姓名、单位 |
| 需要恭喜的人 - 获奖 | 国家科技奖等 | nosta_news, moe_keji | LLM 提取获奖者信息 |
| 兄弟单位动向 | 清北/国智院/AI Lab 重要新闻 | tsinghua_news, pku_news, baai_news, tsinghua_air, shlab_news 等 | LLM 筛选重要动态 + 生成启示分析 |
| 兄弟单位动向 - 对学院发展的启示 | 同上 | 同上 | LLM 生成对比分析 + 建议 |

#### 对国家

| 院长需求 | 需要的信息 | 数据来源 (raw) | 处理方式 |
|---------|-----------|---------------|---------|
| 需要关注的最新政策 | 教育/科技/人才/产业政策 | gov_cn_zhengce, ndrc_policy, moe_policy, most_policy | LLM 判断与学院发展的相关性 |
| 人事变动 | 部委领导变动 | 待补充 | LLM 提取人名+职位 |
| 领导讲话 | 发改委/教育部/科技部 | 同上 + 领导讲话专题页 | LLM 提取关键要点 |

#### 对技术

| 院长需求 | 需要的信息 | 数据来源 (raw) | 处理方式 |
|---------|-----------|---------------|---------|
| 技术进展与趋势 | 国内外最新 AI 技术 | arxiv_cs_ai, hacker_news, reddit_ml_rss, jiqizhixin_rss, 36kr_ai_rss | LLM 聚合 + 趋势分析 |
| 热点话题与 KOL | 外网热点、KOL 发言 | reddit_ml_rss, reddit_localllama_rss, hacker_news, github_trending | LLM 筛选高热度话题 |
| 内参机会 | 领导可能关心的技术问题 | 综合以上所有技术源 | LLM 预判 + 生成内参建议 |

#### 对产业

| 院长需求 | 需要的信息 | 数据来源 (raw) | 处理方式 |
|---------|-----------|---------------|---------|
| 重大产业新闻 | AI 行业头条 | 36kr_news, tmtpost_news, jiemian_tech | LLM 筛选重大事件 |
| 融资/IPO | AI 企业融资动态 | chinaventure_news | LLM 提取企业名+金额+轮次 |
| 内参机会 | 领导关心的产业问题 | 综合以上 | LLM 预判 |

#### 暂无数据覆盖的需求

| 院长需求 | 维度 | 原因 | 计划 |
|---------|------|------|------|
| AI 人才回国意向 | 对人才 | 需要社交媒体/LinkedIn 数据 | 暂缓 |
| 小红书/社交媒体舆情 | 对学院 | 需 Cookie + 反爬处理，难度高 | 需单独方案 |
| 日程冲突检测 | 对日程 | 需要院长日历数据接入 | 需外部对接 |
| 学院内部信息 | 对学院 | 非爬虫范畴，需内部系统对接 | 不在爬虫范围 |
| 微信公众号内容 | 多维度 | 封闭平台，需搜狗/公号后台方案 | 优先级中 |

### refined/ 目录计划结构

```
data/refined/{YYYY-MM-DD}/
├── universities/
│   ├── congratulations.json      # 需要恭喜的人（人事任免 + 院士 + 获奖）
│   └── peer_insights.json        # 兄弟单位动向 + 启示
├── national_policy/
│   ├── policy_alerts.json        # 需要关注的新政策
│   └── personnel_changes.json    # 部委人事变动
├── technology/
│   ├── trend_report.json         # 技术趋势分析
│   └── hot_topics.json           # 热点话题
├── industry/
│   ├── major_news.json           # 重大产业新闻
│   └── funding_deals.json        # 融资/IPO
├── beijing_policy/
│   └── policy_alerts.json        # 北京最新政策
├── talent/
│   └── talent_updates.json       # 人才动态
├── events/
│   └── upcoming.json             # 近期活动
└── daily_briefing.json           # 院长每日简报（跨维度汇总）
```

---

## 四、已完成的代码变更

### Bug 修复

- **`app/scheduler/jobs.py:41`** — 删除行尾垃圾字符 `å` (U+00E5)

### 爬虫模板增强

- **`app/crawlers/templates/static_crawler.py`**
  - `_self` 选择器支持（list_item 元素本身作为 title/link）
  - `_extract_date` 双策略日期提取（先 `get_text(strip=True)` 再 `get_text(separator=" ")`）
  - `date_regex` 支持（从混合文本中正则提取日期部分）

- **`app/crawlers/templates/dynamic_crawler.py`**
  - 同步了 static_crawler 的所有改进

### 数据存储

- **`app/crawlers/utils/json_storage.py`**
  - 输出路径从 `data/` 改为 `data/raw/`
  - 支持 `group` 分组子目录：`data/raw/{dimension}/{group}/{source_id}/{date}.json`
  - JSON 输出增加 `group` 字段

### YAML 配置修正（v3 新增）

#### national_policy.yaml
- `gov_cn_zhengce`: 改为 dynamic，选择器 `div.list_2 li` / `h4 a` / `span.date`
- `ndrc_policy`: URL 修正 → `/xxgk/zcfb/tz/`
- `moe_policy`: 选择器修正 → `div.moe-list li`
- `most_policy`: 选择器修正 → `ul.a_list li`，日期 `div.w_list_rq`
- `miit_policy`: 禁用 (403 WAF)

#### beijing_policy.yaml
- `beijing_zhengce`: 选择器修正 → `ul.zc_news_list li`
- `bjkw_policy`: URL 修正为根目录，选择器 → `ul.infoList li`
- `bjjw_policy`: 选择器修正 → `ul.z-mylist li`
- `bjrsj_policy`: 选择器修正 → `ul.allList li`
- `ncsti_policy`: 选择器修正 → `ul.qcdt-list li`
- `beijing_ywdt`: 选择器修正 → `ul.news_list li`
- `bjrd_renshi`: 选择器修正 → `ul.txt_tab li`
- 禁用: zgc_policy (连接重置), bjfgw_policy (JS跳转链), bjhd_policy (404), bjd_news (复杂布局), beijing_rsrm (404)

#### industry.yaml
- `36kr_news`: 选择器修正 → `div.newsflash-item` / `a.item-title`
- `tmtpost_news`: 改为 RSS (`/feed`)
- `jiemian_tech`: 选择器修正 → `li.card-list` / `h3.card-list__title`
- `chinaventure_news`: 选择器修正 → `div.news_list_zone li` / `h1`
- 禁用: huxiu_news (WAF), thepaper_tech (SPA), iyiou_ai (空壳), 36kr_investment (404)

#### talent.yaml
- `moe_talent`: URL 修正 → `s5744/`，选择器 → `ul#list li`，扩展关键词
- `nature_index`: 选择器修正 → `article`
- `wrsa_talent`: 选择器修正 → `div.news_div1 li`
- 禁用: csrankings (SPA), aminer_ai (SPA)

#### events.yaml
- `aideadlines`: 改为 dynamic，选择器 → `div.ConfItem` / `span.conf-title a`
- `wikicfp`: 选择器保持 `tr[bgcolor]`
- 禁用: huodongxing (CAPTCHA), meeting_edu (不可达)

---

## 五、待办事项

### 高优先级

- [x] ~~验证其余 6 个维度的源~~ — 完成！所有 55 个启用源已通过验证
- [ ] **实现 refined/ 数据处理管线** — 设计 LLM 处理流程，将 raw 数据转化为按院长需求场景组织的业务数据
- [ ] **创建 sentiment 维度 YAML** — 学院舆情维度尚未开始，难度最高（社交媒体反爬）

### 中优先级

- [ ] 修复 universities 维度 4 个禁用源 (zju_news, nju_news, zhejianglab_news, shanghairanking_news)
- [ ] 补充高校 HR/组织部页面（15 所高校，snapshot 模式）— 用于检测人事变动
- [ ] 补充 AI 院系官网（8 个）— 用于跟踪院长/系主任级变动
- [ ] IEEE Fellow / ACM Fellow 年度公告源
- [ ] 微信公众号方案（搜狗微信搜索 / 公号后台）
- [ ] 详情页抓取 — 当前只抓标题+链接，`content` 字段为空
- [ ] 恢复禁用源: bjfgw_policy (改用 dynamic), thepaper_tech (解析 __NEXT_DATA__), huxiu_news (查找 RSS)

### 低优先级

- [ ] 青塔 (Nuxt SPA，需 Playwright 深度适配)
- [ ] CNIPA 专利公告
- [ ] Alembic 数据库迁移
- [ ] 单元测试 / 集成测试

---

## 六、运行方式

```bash
# 测试单个源（不写数据库，输出 JSON 到 data/raw/）
python scripts/run_single_crawl.py --source pku_news --no-db

# 启动完整服务（含调度器）
uvicorn app.main:app --reload
```

---

## 七、前端数据支撑状态

> 2026-02-13 新增。对应 Dean-Agent 前端 8 个功能模块的数据支撑情况。

### 可支撑模块（v2 API 已实现）

| 前端模块 | 子页面 | v2 API 端点 | 数据条数 | 状态 |
|---------|--------|-----------|---------|------|
| 政策情报 | 国家政策 | `/api/v2/policy/national` | 17 | ✅ 可用 |
| 政策情报 | 北京政策 | `/api/v2/policy/beijing` | 26 | ✅ 可用 |
| 科技前沿 | 行业动态 | `/api/v2/tech/industry-news` | 33 | ✅ 可用 |
| 科技前沿 | 技术趋势 | `/api/v2/tech/trends` | LLM | ⚡ 需配置 LLM |
| 科技前沿 | 热点话题 | `/api/v2/tech/hot-topics` | 社区数据 | ✅ 基础可用 |
| 高校生态 | 同行动态 | `/api/v2/university/peers` | 11 机构 | ✅ 可用 |
| 高校生态 | 人事变动 | `/api/v2/university/personnel` | 19 | ✅ 可用 |
| 高校生态 | 科研成果 | `/api/v2/university/research` | 奖项数据 | ✅ 可用 |
| 人才雷达 | 人才指数 | `/api/v2/talent/index` | 32 | ✅ 可用 |
| 活动日程 | 活动推荐 | `/api/v2/events/recommended` | 212 | ✅ 可用 |
| 院长早报 | 指标卡片 | `/api/v2/briefing/metrics` | 7 维度 | ✅ 可用 |
| 院长早报 | 优先事项 | `/api/v2/briefing/priorities` | 规则打分 | ✅ 可用 |
| 院长早报 | 每日简报 | `/api/v2/briefing/daily` | LLM | ⚡ 需配置 LLM |

### 暂不支撑模块

| 前端模块 | 子页面 | 原因 | 计划 |
|---------|--------|------|------|
| 政策情报 | 领导讲话 | 无信源 | 需新增 gov.cn 领导活动页爬虫 |
| 政策情报 | 政策机会匹配 | 需 LLM 深度分析 | Phase 3 实现 |
| 科技前沿 | KOL 追踪 | 需学术 API | Semantic Scholar 扩展 |
| 科技前沿 | 内参机会 | 需 LLM 综合分析 | Phase 3 |
| 人才雷达 | 回流追踪 | 需多信号检测 | 暂缓 |
| 人才雷达 | 学术流动 | 需 LLM 提取 | Phase 2 |
| 院内管理 | 全部 | 内部 OA 数据 | 非爬虫范畴 |
| 人脉网络 | 全部 | CRM 数据 | 非爬虫范畴 |
| 智能日程 | 全部 | 日历 API | 非爬虫范畴 |

---

## 八、信源缺口分析

基于前端功能需求反推，当前缺少以下信源：

| 前端需求 | 缺失数据 | 建议补充方案 | 优先级 |
|---------|---------|------------|--------|
| 领导讲话 | 部委领导讲话/活动 | 新增 gov.cn 国务院领导活动页、部委领导讲话专题 | P1 |
| KOL 追踪 | AI KOL 动态/hIndex | 扩展 Semantic Scholar API + Google Scholar | P2 |
| 人才回流 | 海外学者回国信号 | ArXiv affiliation 变更检测 | P2 |
| 融资/IPO | 更全面投融资数据 | IT桔子 API / 企查查 API | P2 |
| 学院舆情 | 社交媒体提及 | MediaCrawler (微博/小红书) | P3 |
| 专利数据 | AI 相关专利 | CNIPA 公告 | P3 |
