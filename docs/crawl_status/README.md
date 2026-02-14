# 信源爬取状态总览

> 最后更新: 2026-02-14 (v8: 修复详情页 URL 404 — base_url 解析 bug，影响 9 个信源)
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
| personnel | `state_council` | 国务院人事任免 | 1 |
| personnel | `moe` | 教育部人事任免 | 2 |
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

**注意**: 已为 33 个信源配置 `detail_selectors`，这些源的条目会自动抓取详情页正文填充 `content` / `summary` 字段。其余源（RSS 源已自带正文、自定义 Parser 源通过 API 获取）也有内容。v8 已修复 base_url 解析 bug，moe.gov.cn、ndrc、most、bjjw 等详情页 URL 404 问题已解决。

### refined/ 数据说明

尚未实现。该目录用于存放经过 LLM 处理后的业务数据，按院长需求场景组织。具体设计见下方「三、从原始数据到业务数据」。

### 数据质量实况（2026-02-14 基于实际数据文件统计）

> **核心问题**: 配了 detail_selectors 不等于有数据。只有重新爬取过的源才有正文。旧数据文件里仍是空的。

#### 🟢 能爬到完整数据（标题 + 正文）— 19 个源

| 维度 | source_id | 名称 | 正文来源 |
|------|-----------|------|---------|
| technology | arxiv_cs_ai | ArXiv cs.AI | API Parser (abstract) |
| technology | github_trending | GitHub Trending | API Parser (description) |
| technology | reddit_ml_rss | Reddit r/MachineLearning | RSS 自带正文 |
| technology | reddit_localllama_rss | Reddit r/LocalLLaMA | RSS 自带正文 |
| technology | 36kr_ai_rss | 36氪-AI频道 | RSS 自带正文 |
| technology | mit_tech_review_rss | MIT Technology Review | RSS 自带正文 |
| technology | techcrunch_ai_rss | TechCrunch AI | RSS 自带正文 |
| industry | tmtpost_news | 钛媒体 | RSS 自带正文 |
| industry | jiemian_tech | 界面新闻-科技 | detail_selectors 已验证 |
| industry | chinaventure_news | 投中网 | detail_selectors 已验证 |
| industry | 36kr_news | 36氪-快讯 | detail_selectors 已验证（部分 CSR 页面无效） |
| personnel | mohrss_rsrm | 人社部-国务院人事任免 | detail_selectors + Playwright |
| talent | wrsa_talent | 欧美同学会 | detail_selectors 已验证 |
| talent | semantic_scholar_ai | Semantic Scholar | API Parser (abstract, 11/20) |
| universities | tsinghua_news | 清华大学新闻网 | detail_selectors 已验证 |
| universities | ia_cas_news | 中科院自动化所 | detail_selectors 已验证 |
| universities | zhejiang_jyt | 浙江省教育厅 | detail_selectors 已验证 |
| beijing_policy | bjkw_policy | 北京市科委/中关村管委会 | detail_selectors 已验证 |
| technology | hacker_news | Hacker News | API Parser (1/7 有正文) |

#### 🟠 已配置 detail_selectors，重爬后即可有正文 — 22 个源

这些源的 YAML 已配置了正确的 CSS 选择器，但当前 `data/raw/` 里的 JSON 文件是旧数据（配置前爬的），需要重新跑一次 `run_single_crawl.py` 或等定时任务自动爬取。

| 维度 | 源 | 选择器 |
|------|---|--------|
| universities | pku_news, ustc_news, sjtu_news, fudan_news | 各站不同 |
| universities | baai_news, tsinghua_air, shlab_news, pcl_news, ict_cas_news | 各站不同 |
| universities | eol_news, jyb_news, cas_news, cae_news | 各站不同 |
| universities | shanghai_jw, jiangsu_jyt, guangdong_jyt | 省教育厅 |
| beijing_policy | beijing_zhengce, bjjw_policy, bjrsj_policy, ncsti_policy, beijing_ywdt, bjrd_renshi | 统一 `div.TRS_UEDITOR` |

#### 🔴 仅有标题+URL，正文为空 — 约 15 个源

| 原因 | 影响源 |
|------|--------|
| ~~moe.gov.cn 详情页 URL 404~~ | ~~moe_renshi, moe_renshi_si, moe_talent, moe_policy~~ (v8 已修复) |
| ~~国家部委详情页 URL 404~~ | ~~ndrc_policy, most_policy~~ (v8 已修复) |
| **RSS 不含正文** | jiqizhixin_rss (1源) |
| **会议列表页，非文章** | aideadlines, wikicfp (2源) |
| **暂未配置 detail_selectors** | nature_index, nosta_news, moe_keji, beijing_jw (4源) |
| **gov_cn_zhengce 无关键词匹配** | gov_cn_zhengce (1源，0条数据) |

#### 数据汇总

```
总数据文件: 56 个 (跨 9 个维度)
总条目数:   696 条
有正文:     209 条 (30%)  ← 重爬后预计可达 ~80%
仅标题:     487 条 (70%)  ← 大部分是旧数据，重爬后会填充
```

---

## 二、各维度爬取状态

### 总览

| 维度 | 计划源数 | 已配置 | 已启用 | 已验证通过 | 产出数据 | YAML 文件 |
|------|---------|--------|--------|-----------|---------|----------|
| personnel (对人事) | ~3 | 3 | 3 | **3/3** | ✅ | `sources/personnel.yaml` |
| universities (对高校) | ~33 | 26 | 22 | **22/22** | ✅ | `sources/universities.yaml` |
| technology (对技术) | ~23 | 12 | 10 | **10/10** | ✅ | `sources/technology.yaml` |
| national_policy (对国家) | ~21 | 6 | 4 | **4/4** | ✅ 3源有数据 | `sources/national_policy.yaml` |
| beijing_policy (对北京) | ~14 | 12 | 7 | **7/7** | ✅ 6源有数据 | `sources/beijing_policy.yaml` |
| industry (对产业) | ~13 | 8 | 4 | **4/4** | ✅ 3源有数据 | `sources/industry.yaml` |
| talent (对人才) | ~10 | 7 | 4 | **4/4** | ✅ 3源有数据 | `sources/talent.yaml` |
| twitter (跨维度监控) | — | 7 | 7 | 未验证 | ⚠️ 需 API key | `sources/twitter.yaml` |
| sentiment (对学院舆情) | ~6 | 0 | 0 | N/A | — | 未创建 |
| events (对日程) | ~4 | 4 | 2 | **2/2** | ✅ 2源有数据 | `sources/events.yaml` |
| **合计** | **~127** | **85** | **63** | **56/63** | — | — |

> **说明**: "已验证通过"指所有启用源 (is_enabled: true) 的选择器已确认匹配实际页面 HTML 结构。部分源因当前页面无关键词匹配条目而产出 0 条数据（如 gov_cn_zhengce、36kr_news），但选择器和爬虫逻辑均已验证正确，待相关内容出现时将自动采集。

### 详细状态：personnel (对人事) — 已全量验证 (2026-02-14 新增)

**3/3 启用源全部通过实际运行验证**

#### A. 国务院人事任免
| source_id | 名称 | 方法 | 条目数 | 详情页 | 说明 |
|-----------|------|------|--------|--------|------|
| mohrss_rsrm | 人社部-国务院人事任免 | dynamic | 20 | ✅ 正文提取 | Playwright 绕过 JS 反爬，detail_selectors 抓取 `div.TRS_Editor` 正文 |

#### B. 教育部人事任免
| source_id | 名称 | 方法 | 条目数 | 日期 | 详情页 | 说明 |
|-----------|------|------|--------|------|--------|------|
| moe_renshi | 教育部-人事任免 | static | 20 | yes | ✅ 已修复 | v8: 删除错误的 domain-only base_url，回退到 url 字段 |
| moe_renshi_si | 教育部-人事司公告 | static | 7 | yes | ✅ 已修复 | v8: 同上 |

> **DynamicPageCrawler detail_selectors**: 本次新增了 DynamicPageCrawler 对 `detail_selectors` 的支持，可在 Playwright 抓取列表页后，复用同一浏览器上下文逐条进入详情页提取正文。mohrss_rsrm 是首个使用此功能的信源。

### 详细状态：universities (对高校) — 已全量验证 + 详情页正文抓取

**22/22 启用源全部通过实际运行验证 (2026-02-13)。19 个源已配置 detail_selectors，可抓取详情页正文。**

> 注：moe_renshi、moe_renshi_si 已于 2026-02-14 迁移至 personnel 维度。

#### A. 高校新闻网
| source_id | 名称 | 方法 | 条目数 | 详情页 | content selector |
|-----------|------|------|--------|--------|-----------------|
| tsinghua_news | 清华大学新闻网 | static | 10 | ✅ | `div.content` |
| pku_news | 北京大学新闻网 | dynamic | 10 | ✅ | `div.article` |
| ustc_news | 中国科大新闻网 | static | 30 | ✅ | `div.article-content` |
| sjtu_news | 上海交大新闻网 | static | 46 | ✅ | `div.info` |
| fudan_news | 复旦大学新闻网 | static | 16 | ✅ | `div.article` |

#### C. AI 研究机构
| source_id | 名称 | 方法 | 条目数 | 详情页 | content selector |
|-----------|------|------|--------|--------|-----------------|
| baai_news | BAAI 智源社区 | dynamic | 6 | ✅ | `div.post-content` |
| tsinghua_air | 清华 AIR | static | 16 | ✅ | `div.v_news_content` |
| shlab_news | 上海 AI 实验室 | dynamic | 7 | ✅ | `#lightgallery` |
| pcl_news | 鹏城实验室 | static | 10 | ✅ | `div.article` |
| ia_cas_news | 中科院自动化所 | static | 37 | ✅ | `div.trs_editor_view` |
| ict_cas_news | 中科院计算所 | static | 6 | ✅ | `#xlmain` |

#### D. 高教新闻聚合
| source_id | 名称 | 方法 | 条目数 | 详情页 | content selector |
|-----------|------|------|--------|--------|-----------------|
| eol_news | 中国教育在线 | static | 1 | ✅ | `div.article` |
| jyb_news | 中国教育报 | static | 21 | ✅ | `div.xl_text` |

#### E. 科技成果与荣誉
| source_id | 名称 | 方法 | 条目数 | 详情页 | content selector |
|-----------|------|------|--------|--------|-----------------|
| cas_news | 中国科学院 | static | 1 | ✅ | `div.trs_editor_view` |
| cae_news | 中国工程院 | static | 6 | ✅ | `#info_content` |
| nosta_news | 国家科技奖励办 | dynamic | 6 | — | 暂无 |
| moe_keji | 教育部科技司 | static | 7 | — | 暂无 |

#### F. 省级教育厅
| source_id | 名称 | 方法 | 条目数 | 详情页 | content selector |
|-----------|------|------|--------|--------|-----------------|
| beijing_jw | 北京市教委 | static | 1 | — | 暂无 |
| shanghai_jw | 上海市教委 | static | 2 | ✅ | `#ivs_content` |
| zhejiang_jyt | 浙江省教育厅 | static | 7 | ✅ | `#zoom` |
| jiangsu_jyt | 江苏省教育厅 | static | 6 | ✅ | `#zoom` |
| guangdong_jyt | 广东省教育厅 | static | 2 | ✅ | `div.article` |

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

### 详细状态：beijing_policy (对北京) — 已验证 + 详情页正文抓取

**7/12 源启用，6 源产出数据。7 个启用源全部配置 detail_selectors（统一使用 TRS CMS `div.TRS_UEDITOR`）。**

#### A. 政策文件
| source_id | 名称 | 方法 | 启用 | 条目数 | 详情页 | 说明 |
|-----------|------|------|------|--------|--------|------|
| beijing_zhengce | 首都之窗-政策文件 | dynamic | ✅ | 1 | ✅ | detail_use_playwright: false (httpx 抓详情) |
| bjkw_policy | 北京市科委/中关村管委会 | static | ✅ | 4 | ✅ 验证通过 | 全文正文已抓取 |
| bjjw_policy | 北京市教委 | static | ✅ | 14 | ✅ | TRS CMS |
| bjrsj_policy | 北京市人社局 | static | ✅ | 1 | ✅ | TRS CMS |
| zgc_policy | 中关村示范区 | static | ❌ | — | — | 域名连接被重置 |
| ncsti_policy | 国际科创中心 | static | ✅ | 5 | ✅ | TRS CMS |
| bjfgw_policy | 北京市发改委 | static | ❌ | — | — | 多级 JS 跳转链 |
| bjhd_policy | 海淀区政府 | static | ❌ | — | — | `/zwgk/` 返回 404 |

#### B. 人事变动与要闻
| source_id | 名称 | 方法 | 启用 | 条目数 | 详情页 | 说明 |
|-----------|------|------|------|--------|--------|------|
| beijing_ywdt | 首都之窗-要闻 | static | ✅ | 0* | ✅ | TRS CMS，选择器已配置 |
| bjd_news | 北京日报 | static | ❌ | — | — | 首页布局复杂 |
| bjrd_renshi | 北京市人大常委会 | static | ✅ | 1 | ✅ | TRS CMS |
| beijing_rsrm | 首都之窗-人事任免 | static | ❌ | — | — | URL 返回 404 |

> \* beijing_ywdt 选择器已验证正确，0 条是因为当前首页要闻标题不包含 AI/教育/科技等关键词。

### 详细状态：industry (对产业) — 已验证 + 详情页正文抓取

**4/8 源启用，3 源产出数据。3 个源配置 detail_selectors。**

#### A. 产业新闻
| source_id | 名称 | 方法 | 启用 | 条目数 | 详情页 | content selector |
|-----------|------|------|------|--------|--------|-----------------|
| 36kr_news | 36氪-快讯 | static | ✅ | 3 | ✅ 部分 | `div.item-desc`（SSR 渲染的有正文，CSR 的无） |
| huxiu_news | 虎嗅 | static | ❌ | — | — | WAF 反爬 |
| tmtpost_news | 钛媒体 | rss | ✅ | 3 | ✅ RSS 自带 | RSS feed 已含正文 |
| jiemian_tech | 界面新闻-科技 | static | ✅ | 3 | ✅ 验证通过 | `div.article-content` |
| thepaper_tech | 澎湃新闻-科技 | static | ❌ | — | — | Next.js SPA |
| iyiou_ai | 亿欧-AI | static | ❌ | — | — | 空壳页面 |

#### B. 融资/IPO
| source_id | 名称 | 方法 | 启用 | 条目数 | 详情页 | content selector |
|-----------|------|------|------|--------|--------|-----------------|
| chinaventure_news | 投中网 | static | ✅ | 8 | ✅ 验证通过 | `div.article_slice_pc` |
| 36kr_investment | 36氪-融资频道 | static | ❌ | — | — | URL 已下线 |

### 详细状态：talent (对人才) — 已验证 + 详情页正文抓取

**4/7 源启用，3 源产出数据。2 个源配置 detail_selectors。**

#### A. 人才追踪
| source_id | 名称 | 方法 | 启用 | 条目数 | 详情页 | 说明 |
|-----------|------|------|------|--------|--------|------|
| csrankings | CSRankings | static | ❌ | — | — | React SPA |
| semantic_scholar_ai | Semantic Scholar-AI论文 | API | ✅ | 0† | ✅ API 自带 | 自定义 Parser 获取论文摘要 |
| nature_index | Nature Index | static | ✅ | 4 | — | 暂无 detail_selectors |
| aminer_ai | AMiner-AI学者 | static | ❌ | — | — | JS SPA |

#### B. 人才政策公示
| source_id | 名称 | 方法 | 启用 | 条目数 | 详情页 | content selector |
|-----------|------|------|------|--------|--------|-----------------|
| nsfc_talent | NSFC杰青/优青公示 | static | ❌ | — | — | URL 404 |
| moe_talent | 教育部人才计划公示 | static | ✅ | 6 | ✅ 已修复 | v8: base_url 补 trailing slash，URL 解析正确 |
| wrsa_talent | 欧美同学会 | static | ✅ | 2 | ✅ 验证通过 | `#Content` |

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
| 需要恭喜的人 - 人事变动 | 高校校长/院长/书记任免 | **personnel 维度**: mohrss_rsrm (含正文), moe_renshi, moe_renshi_si + 高校新闻网 | LLM 从正文/标题识别人事变动，提取人名+职位+学校 |
| 需要恭喜的人 - 院士 | 院士增选/Fellow 当选 | cas_news, cae_news | LLM 提取当选者姓名、单位 |
| 需要恭喜的人 - 获奖 | 国家科技奖等 | nosta_news, moe_keji | LLM 提取获奖者信息 |
| 兄弟单位动向 | 清北/国智院/AI Lab 重要新闻 | tsinghua_news, pku_news, baai_news, tsinghua_air, shlab_news 等 | LLM 筛选重要动态 + 生成启示分析 |
| 兄弟单位动向 - 对学院发展的启示 | 同上 | 同上 | LLM 生成对比分析 + 建议 |

#### 对国家

| 院长需求 | 需要的信息 | 数据来源 (raw) | 处理方式 |
|---------|-----------|---------------|---------|
| 需要关注的最新政策 | 教育/科技/人才/产业政策 | gov_cn_zhengce, ndrc_policy, moe_policy, most_policy | LLM 判断与学院发展的相关性 |
| 人事变动 | 部委领导变动 | **personnel 维度**: mohrss_rsrm (国务院任免，含正文) | LLM 提取人名+职位 |
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
├── personnel/
│   └── appointments.json         # 人事任免（人名+职位+单位，AI 从 raw 正文提取）
├── national_policy/
│   ├── policy_alerts.json        # 需要关注的新政策
│   └── personnel_changes.json    # 部委人事变动（引用 personnel 维度数据）
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

### personnel 维度新增 + DynamicPageCrawler 增强（v4 新增）

- **`sources/personnel.yaml`** — 新增维度，含 3 个信源：
  - `mohrss_rsrm`: 人社部-国务院人事任免（dynamic + detail_selectors）
  - `moe_renshi`: 教育部-人事任免（从 universities.yaml 迁移）
  - `moe_renshi_si`: 教育部-人事司公告（从 universities.yaml 迁移）

- **`app/crawlers/templates/dynamic_crawler.py`**
  - 新增 `detail_selectors` 支持（与 StaticHTMLCrawler 对齐）
  - `_fetch_detail_with_playwright()`: 复用同一浏览器上下文，共享 cookie 绕过反爬
  - `_fetch_detail_with_httpx()`: 备选方案，适用于无 JS 保护的详情页
  - `detail_use_playwright` 配置项控制（默认 true）
  - 等待策略: `load` + `networkidle` 组合，确保 JS 反爬执行完毕

- **`app/api/v1/dimensions.py`** — DIMENSION_NAMES 新增 `"personnel": "对人事"`
- **`app/main.py`** — FastAPI description 更新为 9 个维度

### 详情页正文抓取配置（v6 新增）

为 33 个信源添加 `detail_selectors`，使爬虫自动抓取详情页正文填充 `content` / `summary` 字段：

| 维度 | 源数 | 选择器模式 | 验证状态 |
|------|------|-----------|---------|
| universities | 19 | 各站不同（`div.content`, `div.article`, `#zoom` 等） | ✅ tsinghua_news, ia_cas_news, zhejiang_jyt 验证通过 |
| beijing_policy | 7 | 统一 `div.TRS_UEDITOR`（北京政务 TRS CMS） | ✅ bjkw_policy 验证通过 |
| industry | 3 | `div.item-desc`, `div.article-content`, `div.article_slice_pc` | ✅ jiemian_tech, chinaventure_news 验证通过 |
| talent | 2 | `#Content`, `div.TRS_UEDITOR` | ✅ wrsa_talent 验证通过 |
| personnel | 2 | `div.TRS_UEDITOR`（mohrss_rsrm 已有 `div.TRS_Editor`） | ✅ v8 已修复 URL 404 |

**已知问题**:
- ~~moe.gov.cn 详情页 URL 404~~ — v8 已修复，根因是 base_url 配置错误导致 urljoin 丢失路径段
- 36kr 快讯部分页面为 CSR 渲染，httpx 无法获取正文（仅 SSR 页面有效）

### 全量代码 Review（v7 新增）

#### 消除代码重复
- **新建 `app/crawlers/utils/selector_parser.py`** — 提取 static/dynamic 爬虫共享的 3 个函数：
  - `extract_date(el, selectors)`: 日期提取（含 `date_regex` 支持）
  - `parse_list_items(soup, selectors, base_url, keyword_filter)`: 列表页解析（含 `_self` 约定）
  - `parse_detail_html(html, detail_selectors)`: 详情页正文解析
- **`static_crawler.py`** 从 181 行精简到 93 行，调用公共函数
- **`dynamic_crawler.py`** 从 226 行精简到 127 行，调用公共函数
- **`http_client.py`** 提取内部 `_request_with_retry()` 函数，消除 `fetch_page` / `fetch_json` 重复

#### 修复 P0 Bug
- **`scheduler/jobs.py`** — Article 插入改用 `INSERT ... ON CONFLICT DO NOTHING`（修复 url_hash UNIQUE 约束冲突导致整个事务回滚）
- **`crawlers/base.py`** — 空结果 status 从 `SUCCESS` 改为 `NO_NEW_CONTENT`
- **`main.py`** — 去掉 CORS 无效组合 `allow_credentials=True`（与 `allow_origins=["*"]` 冲突）；Playwright 关闭异常加日志

#### 统一架构分层
- **新建 `app/services/dimension_service.py`** — `DIMENSION_NAMES` + `list_dimensions()` 从 API 层下沉到 service 层
- **`api/v1/dimensions.py`** — 调用 service，不再直接写 SQLAlchemy 查询
- **`api/deps.py`** — 删除冗余 `get_db_session`（仅是 `get_db` 的透传）
- **`schemas/article.py`** — 删除死字段 `q`（在 deps 中接收但 service 层从未使用）
- 所有 API 端点统一用 `Depends(get_db)` 替代 `Depends(get_db_session)`

#### 性能优化
- **`playwright_pool.py`** — 加 `asyncio.Semaphore(settings.PLAYWRIGHT_MAX_CONTEXTS)` 限制并发上下文
- **`http_client.py`** — `httpx.AsyncClient` 提到 retry 循环外，避免每次重试创建新连接

#### 安全加固
- **`article_service.py`** — 加 `_ALLOWED_SORT_FIELDS` 白名单，防止任意列名注入

#### 路径约定统一
- **`json_storage.py`** — 新增 `build_source_dir()` 函数统一路径构建
- **`json_reader.py`** — 引用 `json_storage.DATA_DIR` 而非自行定义

### 详情页 URL 404 修复（v8 新增）

#### 根因
`urljoin(base_url, raw_link)` 在 `selector_parser.py` 中构造详情页 URL 时，因 base_url 配置错误产生 404：
- **Pattern 1**: base_url 缺少 trailing slash（如 `.../s5744`），urljoin 将末段当作文件名丢弃
- **Pattern 2**: base_url 仅为域名（如 `https://www.moe.gov.cn`），相对链接解析到域名根路径

#### 代码修复
- **`app/crawlers/utils/selector_parser.py`** — 新增 `_normalize_base_url()` 函数，在 `parse_list_items()` 入口自动补全 trailing slash，防止 urljoin 丢失路径段

#### YAML 修复（9 源）
- **Pattern 2 (删除错误 base_url)**: moe_renshi, moe_renshi_si (personnel.yaml), bjjw_policy, bjrsj_policy (beijing_policy.yaml)
- **Pattern 1 (补 trailing slash)**: moe_talent (talent.yaml), ndrc_policy, moe_policy, most_policy (national_policy.yaml), beijing_zhengce (beijing_policy.yaml)

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
- [x] ~~详情页抓取~~ — 已为 33 个信源配置 detail_selectors（universities 19, beijing_policy 7, industry 3, talent 2, personnel 2）。仅 national_policy 因 URL 失效暂未配置。
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

> 2026-02-14 更新。v2 业务 API 层已删除，当前仅有 v1 通用 API。

### 当前可用 API（v1）

v1 API 提供通用数据查询能力，前端可通过 dimension 参数按维度筛选数据：

| 端点 | 功能 | 前端可用方式 |
|------|------|------------|
| `GET /api/v1/articles?dimension=X` | 按维度查询文章列表 | 各模块数据源 |
| `GET /api/v1/articles/search?q=X` | 全文搜索 | 搜索功能 |
| `GET /api/v1/articles/stats` | 按维度/源聚合统计 | 指标卡片 |
| `GET /api/v1/dimensions` | 9 维度概览 + 文章数 | 首页总览 |
| `GET /api/v1/dimensions/{dim}` | 单维度文章（支持 keyword） | 维度详情页 |
| `GET /api/v1/sources` | 信源列表 + 状态 | 信源管理 |
| `GET /api/v1/health/crawl-status` | 爬取状态总览 | 系统监控 |

### 前端功能差距分析

| 前端模块 | 子页面 | v1 能力 | 差距 | 优先级 |
|---------|--------|---------|------|--------|
| 政策情报 | 国家/北京政策 | ✅ dimension 筛选可用 | 无专用聚合视图 | — |
| 科技前沿 | 行业动态 | ✅ dimension 筛选可用 | 无专用聚合视图 | — |
| 科技前沿 | 技术趋势 | ❌ 需 LLM 分析 | 需重建业务 API | P1 |
| 高校生态 | 同行动态 | ✅ dimension 筛选可用 | 无分组聚合 | — |
| 人才雷达 | 人才指数 | ⚠️ 有原始数据 | 需 LLM 加工 | P2 |
| 活动日程 | 活动推荐 | ✅ dimension 筛选可用 | 无推荐排序 | — |
| 院长早报 | 每日简报 | ❌ 需 LLM 生成 | 需重建业务 API | P1 |
| 政策情报 | 领导讲话 | ❌ 无信源 | 需新增信源 | P1 |
| 政策情报 | 政策机会匹配 | ❌ 需 LLM | 需业务 API | P2 |
| 科技前沿 | KOL 追踪 | ❌ 需学术 API 扩展 | Semantic Scholar | P2 |
| 院内管理 | 全部 | ❌ 内部 OA 数据 | 非爬虫范畴 | — |
| 人脉网络 | 全部 | ❌ CRM 数据 | 非爬虫范畴 | — |
| 智能日程 | 全部 | ❌ 日历 API | 非爬虫范畴 | — |

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
