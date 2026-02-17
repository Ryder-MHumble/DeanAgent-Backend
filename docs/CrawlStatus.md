# 信源爬取状态总览

> 最后更新: 2026-02-17

---

## 一、数据目录结构

```
data/raw/{dimension}/{group}/{source_id}/latest.json
```

覆盖模式：每次爬取生成全量条目，通过 `is_new` 标记区分新旧。

### JSON 格式

```json
{
  "source_id": "pku_news",
  "dimension": "universities",
  "group": "university_news",
  "source_name": "北京大学新闻网",
  "crawled_at": "2026-02-15T09:06:32+00:00",
  "previous_crawled_at": "2026-02-14T09:00:00+00:00",
  "item_count": 10,
  "new_item_count": 2,
  "items": [
    {
      "title": "刘志博、王剑威获2026年度陈嘉庚青年科学奖",
      "url": "https://news.pku.edu.cn/xwzh/xxx.htm",
      "url_hash": "7140a069...",
      "published_at": "2026-02-15T00:00:00",
      "author": null,
      "content": "获奖者简介及研究成果...",
      "content_hash": "a3b2c1d0...",
      "source_id": "pku_news",
      "dimension": "universities",
      "tags": ["university", "pku", "news"],
      "extra": {},
      "is_new": true
    }
  ]
}
```

---

## 二、业务智能加工数据 (processed)

原始爬取数据经 `scripts/process_*_intel.py` 加工后，输出到 `data/processed/` 供 API 直接读取。

```
data/processed/
  policy_intel/
    feed.json              # 政策动态 feed（含 matchScore/importance/LLM 增强）
    opportunities.json     # 结构化申报机会（截止日期/资助金额/联系人）
    _enriched/             # 单篇增强结果缓存
    _processed_hashes.json # 增量处理哈希追踪
  personnel_intel/
    feed.json              # 人事动态 feed（含 matchScore/importance/变动列表）
    changes.json           # 结构化人事变动（按人拆分：姓名/职务/部门/动作）
    _processed_hashes.json # 增量处理哈希追踪
```

### 加工管线状态

| 模块 | 脚本 | 方法 | 输入 | 产出 | API 前缀 |
|------|------|------|------|------|---------|
| policy_intel | `scripts/process_policy_intel.py` | 规则 + LLM (两级) | national_policy + beijing_policy 维度 raw JSON | feed.json, opportunities.json | `/api/v1/intel/policy/` |
| personnel_intel | `scripts/process_personnel_intel.py` | 纯规则 (正则提取) | personnel 维度 raw JSON (47篇) | feed.json (47条), changes.json (84人次) | `/api/v1/intel/personnel/` |

```bash
# 运行政策智能加工（Tier 1 规则 + Tier 2 LLM 增强）
python scripts/process_policy_intel.py

# 运行人事情报加工（纯规则，无 LLM 费用）
python scripts/process_personnel_intel.py

# 试运行（不写文件）
python scripts/process_policy_intel.py --dry-run
python scripts/process_personnel_intel.py --dry-run
```

---

## 三、各维度爬取状态

### 总览

| 维度 | 已配置 | 已启用 | 产出数据 | 正文覆盖率 | YAML 文件 |
|------|--------|--------|---------|-----------|----------|
| personnel (对人事) | 4 | 4 | ✅ 47条+ | 97% | `sources/personnel.yaml` |
| universities (对高校) | 55 | 46 | ✅ 584条+ | 78% | `sources/universities.yaml` |
| technology (对技术) | 18+4† | 18+4† | ✅ 272条+ | 96% | `sources/technology.yaml` + twitter |
| national_policy (对国家) | 8 | 6 | ✅ 37条+ | 91% | `sources/national_policy.yaml` |
| beijing_policy (对北京) | 14 | 10 | ✅ 39条+ | 61% | `sources/beijing_policy.yaml` |
| industry (对产业) | 10+1† | 6+1† | ✅ 56条+ | 100% | `sources/industry.yaml` + twitter |
| talent (对人才) | 7+1† | 4+1† | ✅ 49条+ | 81% | `sources/talent.yaml` + twitter |
| sentiment (对学院舆情) | 1† | 1† | ✅ 20条 | 100% | twitter 跨维度 |
| events (对日程) | 6 | 4 | ✅ 212条+ | 0% (会议列表) | `sources/events.yaml` |
| **合计** | **129** | **105** | **1316条+** | **—** | **105 个数据文件** |

> † `sources/twitter.yaml` 的 7 个源按 `dimension` 字段分配到 4 个维度：technology 4源、industry 1源、talent 1源、sentiment 1源。
>
> 部分源正文覆盖率低于 100% 是因为 JSON 合并保留了旧条目（detail_selectors 配置前爬的），删除 `latest.json` 后重爬即可恢复。

### 正文来源分类

78 个启用信源配置 `detail_selectors`，自动抓取详情页正文。其余来源：

| 类型 | 源数 | 说明 |
|------|------|------|
| detail_selectors 抓取 | 77 (1 失效) | 爬虫自动进入详情页提取正文 |
| RSS 自带正文 | 13 | 36kr_ai_rss, mit_tech_review_rss, techcrunch_ai_rss, reddit_ml_rss, reddit_localllama_rss, tmtpost_news, theverge_ai_rss, venturebeat_ai_rss, wired_ai_rss, arstechnica_ai_rss, ieee_spectrum_ai_rss, openai_blog, cyzone_news |
| API Parser | 5 | arxiv_cs_ai/cs_lg/cs_cl (abstract), github_trending (description), semantic_scholar_ai (abstract) |
| Twitter API | 7 | 全部 100% 正文 |
| 结构性无正文 | 4 | jiqizhixin_rss (仅标题), hacker_news (元数据), aideadlines/wikicfp (会议列表) |

> sjtu_news (46 条, 0 正文) 的 `div.info` 选择器可能已失效，需排查。

---

### 详细状态：personnel (对人事) — 4/4 启用

| source_id | 名称 | 方法 | 条目数 | 详情页 | 说明 |
|-----------|------|------|--------|--------|------|
| mohrss_rsrm | 人社部-国务院人事任免 | dynamic | 20 | ✅ | Playwright + detail_selectors `div.TRS_Editor` |
| moe_renshi | 教育部-人事任免 | static | 20 | ✅ | `div.TRS_Editor` (20/20) |
| moe_renshi_si | 教育部-人事司公告 | static | 7 | ✅ | `div.TRS_Editor` (6/7) |
| cas_renshi | 中科院-人事任免 | static | — | ✅ | `div.cobtbox`，关键词过滤任免/人事/选举 |

### 详细状态：universities (对高校) — 46/55 启用

46 个数据文件，584 条目+，453 有正文 (78%)。全部 46 启用源已配置 detail_selectors。

#### A. 高校新闻网 (32 源, 25 启用)

| source_id | 名称 | 方法 | 条目数 | 正文数 | content selector |
|-----------|------|------|--------|--------|-----------------|
| tsinghua_news | 清华大学新闻网 | static | 10 | 10 | `div.content` |
| pku_news | 北京大学新闻网 | dynamic | 10 | 10 | `div.article` |
| ustc_news | 中国科大新闻网 | static | 30 | 30 | `div.article-content` |
| sjtu_news | 上海交大新闻网 | static | 46 | 0 | `div.info` ⚠️ |
| fudan_news | 复旦大学新闻网 | static | 16 | 16 | `div.article` |
| buaa_news | 北京航空航天大学 | static | 5 | 4 | `div.v_news_content` |
| bit_news | 北京理工大学 | static | 21 | 21 | `div.article` |
| bnu_news | 北京师范大学 | static | 5 | 4 | `div.article` |
| ruc_news | 中国人民大学 | dynamic | 9 | 3 | `div.page-content` |
| tju_news | 天津大学 | static | 4 | 4 | `div.v_news_content` |
| tongji_news | 同济大学 | static | 5 | 2 | `div.v_news_content` |
| jlu_news | 吉林大学 | static | 10 | 10 | `#vsb_content_2` |
| hit_news | 哈尔滨工业大学 | static | 14 | 8 | `div.wp_articlecontent` |
| seu_news | 东南大学 | static | 5 | 1 | `div.wp_articlecontent` |
| xmu_news | 厦门大学 | static | 16 | 5 | `div.v_news_content` |
| sdu_news | 山东大学 | static | 19 | 19 | `div.nymain` |
| whu_news | 武汉大学 | static | 6 | 6 | `div.v_news_content` |
| hust_news | 华中科技大学 | static | 6 | 5 | `div.v_news_content` |
| csu_news | 中南大学 | static | 14 | 12 | `div.v_news_content` |
| xidian_news | 西安电子科技大学 | static | 12 | 12 | `div.v_news_content` |
| xjtu_news | 西安交通大学 | static | 45 | 42 | `div.v_news_content` |
| uestc_news | 电子科技大学 | static | 55 | 45 | `div.v_news_content` |
| nudt_news | 国防科技大学 | static | 22 | 22 | `div.pageCon` |
| sysu_news | 中山大学 | dynamic | 11 | 4 | `div.v_news_content` |
| sustech_news | 南方科技大学 | static | 6 | 6 | `div.u-content` |

#### B. AI 研究机构 (11 源, 10 启用)

| source_id | 名称 | 方法 | 条目数 | 正文数 | content selector |
|-----------|------|------|--------|--------|-----------------|
| baai_news | BAAI 智源社区 | dynamic | 9 | 9 | `div.post-content` |
| tsinghua_air | 清华 AIR | static | 16 | 16 | `div.v_news_content` |
| shlab_news | 上海 AI 实验室 | dynamic | 7 | 7 | `#lightgallery` |
| pcl_news | 鹏城实验室 | static | 10 | 10 | `div.article` |
| ia_cas_news | 中科院自动化所 | static | 37 | 34 | `div.trs_editor_view` |
| ict_cas_news | 中科院计算所 | static | 6 | 5 | `#xlmain` |
| sii_news | 上海创智学院 | static | 14 | 14 | `div.wp_articlecontent` |
| slai_news | 深圳河套学院 | static | 6 | 6 | `div.field-item` |
| cesi_news | 电子标准化研究院 | static | — | — | `div.content3` |
| iie_cas_news | 中科院信工所 | static | — | — | `div.about-content` |

#### C. 高教新闻聚合 (3 源, 2 启用)

| source_id | 名称 | 方法 | 条目数 | 正文数 | content selector |
|-----------|------|------|--------|--------|-----------------|
| eol_news | 中国教育在线 | static | 1 | 1 | `div.article` |
| jyb_news | 中国教育报 | static | 40 | 20 | `div.xl_text` |

#### D. 科技成果与荣誉 (4 源, 4 启用)

| source_id | 名称 | 方法 | 条目数 | 正文数 | content selector |
|-----------|------|------|--------|--------|-----------------|
| cas_news | 中国科学院 | static | 1 | 1 | `div.trs_editor_view` |
| cae_news | 中国工程院 | static | 6 | 6 | `#info_content` |
| nosta_news | 国家科技奖励办 | dynamic | 6 | 2 | `div.TRS_UEDITOR` |
| moe_keji | 教育部科技司 | static | 7 | 5 | `div.TRS_Editor` |

#### E. 省级教育厅 (5 源, 5 启用)

| source_id | 名称 | 方法 | 条目数 | 正文数 | content selector |
|-----------|------|------|--------|--------|-----------------|
| beijing_jw | 北京市教委 | static | 1 | 1 | `div.TRS_UEDITOR` |
| shanghai_jw | 上海市教委 | static | 2 | 2 | `#ivs_content` |
| zhejiang_jyt | 浙江省教育厅 | static | 6 | 6 | `#zoom` |
| jiangsu_jyt | 江苏省教育厅 | static | 5 | 5 | `#zoom` |
| guangdong_jyt | 广东省教育厅 | static | 2 | 2 | `div.article` |

#### 禁用源 (9)

| source_id | 名称 | 原因 |
|-----------|------|------|
| zju_news | 浙江大学 | URL 返回错误 |
| nju_news | 南京大学 | SSL 证书问题 |
| bupt_news | 北京邮电大学 | WAF 412 拦截 |
| nankai_news | 南开大学 | 全页面 JS 渲染 |
| nwpu_news | 西北工业大学 | 主页重度 JS 渲染 |
| scu_news | 四川大学 | WAF 412 拦截 |
| lzu_news | 兰州大学 | WAF 412 拦截 |
| zhejianglab_news | 之江实验室 | 复杂 SPA |
| shanghairanking_news | 软科 | URL 404 |

### 详细状态：technology (对技术) — 18/18 启用 + 4 Twitter

#### A. 国内科技媒体 (2 源, 2 启用)

| source_id | 名称 | 方法 | 说明 |
|-----------|------|------|------|
| jiqizhixin_rss | 机器之心 | rss | 仅标题，无正文 |
| 36kr_ai_rss | 36氪-AI频道 | rss | RSS 自带正文 |

#### B. 国际科技源 (8 源, 8 启用)

| source_id | 名称 | 方法 | 说明 |
|-----------|------|------|------|
| techcrunch_ai_rss | TechCrunch AI | rss | RSS 自带正文 |
| theverge_ai_rss | The Verge AI | rss | keyword_filter 过滤 |
| mit_tech_review_rss | MIT Technology Review | rss | RSS 自带正文 |
| venturebeat_ai_rss | VentureBeat AI | rss | **新增** RSS 自带正文 |
| ieee_spectrum_ai_rss | IEEE Spectrum AI | rss | **新增** IEEE 权威技术视角 |
| wired_ai_rss | Wired AI | rss | **新增** keyword_filter 过滤 |
| arstechnica_ai_rss | Ars Technica AI | rss | **新增** 深度技术分析 |

#### C. 公司官方博客 (2 源, 2 启用)

| source_id | 名称 | 方法 | 说明 |
|-----------|------|------|------|
| openai_blog | OpenAI Blog | rss | **恢复**：发现 RSS feed (openai.com/news/rss.xml) |
| anthropic_blog | Anthropic Research | static | **恢复**：SSR 页面，static 可用 |

#### D. ArXiv 论文 (3 源, 3 启用)

| source_id | 名称 | 方法 | 说明 |
|-----------|------|------|------|
| arxiv_cs_ai | ArXiv cs.AI | arxiv_api | AI 综合论文 |
| arxiv_cs_lg | ArXiv cs.LG | arxiv_api | **新增** 机器学习论文 |
| arxiv_cs_cl | ArXiv cs.CL | arxiv_api | **新增** NLP/大模型论文 |

#### E. 社区讨论 (5 源, 5 启用)

| source_id | 名称 | 方法 | 说明 |
|-----------|------|------|------|
| hacker_news | Hacker News | hacker_news_api | 元数据 |
| reddit_ml_rss | Reddit r/MachineLearning | rss | RSS 自带正文 |
| reddit_localllama_rss | Reddit r/LocalLLaMA | rss | RSS 自带正文 |
| github_trending | GitHub Trending | github_api | description |

### 详细状态：national_policy (对国家) — 6/8 启用

全部 6 启用源已配置 detail_selectors。

| source_id | 名称 | 方法 | 启用 | 条目数 | 详情页 | content selector |
|-----------|------|------|------|--------|--------|-----------------|
| gov_cn_zhengce | 国务院-最新政策 | dynamic | ✅ | 20 | ✅ | `div.pages_content` |
| ndrc_policy | 发改委-通知通告 | static | ✅ | 3 | ✅ | `div.TRS_Editor` |
| moe_policy | 教育部-政策法规 | static | ✅ | 8 | ✅ | `div.TRS_Editor` |
| most_policy | 科技部-信息公开 | static | ✅ | 6 | ✅ (3/6) | `div.TRS_UEDITOR` (PDF 项无正文) |
| cac_policy | 国家网信办-政策法规 | static | ✅ | — | ✅ | `div.TRS_Editor` **新增** AI 治理核心监管 |
| samr_news | 国家市监总局-要闻 | static | ✅ | — | ✅ | `#zoom` **新增** 反垄断/AI 监管 |
| miit_policy | 工信部-政策文件 | dynamic | ❌ | — | — | IP 级 WAF 封锁 (403) |
| nsfc_news | 国家自然科学基金委 | static | ❌ | — | — | URL 404 |

### 详细状态：beijing_policy (对北京) — 10/14 启用

10 启用源全部配置 detail_selectors。

#### A. 政策文件

| source_id | 名称 | 方法 | 启用 | 条目数 | 详情页 |
|-----------|------|------|------|--------|--------|
| beijing_zhengce | 首都之窗-政策文件 | dynamic | ✅ | 1 | ✅ |
| bjkw_policy | 北京市科委/中关村管委会 | static | ✅ | 4 | ✅ |
| bjjw_policy | 北京市教委 | static | ✅ | 14 | ✅ |
| bjrsj_policy | 北京市人社局 | static | ✅ | 1 | ✅ |
| zgc_policy | 中关村示范区 | static | ❌ | — | 域名连接被重置 |
| ncsti_policy | 国际科创中心 | static | ✅ | 5 | ✅ |
| bjjxj_policy | 北京市经信局-通知公告 | static | ✅ | — | ✅ `div.TRS_UEDITOR` **新增** AI 政策核心部门 |
| bjzscqj_policy | 北京市知识产权局 | static | ✅ | — | ✅ `div.article-word` **新增** AI 专利/创新基金 |
| bjfgw_policy | 北京市发改委-政策文件 | static | ✅ | — | ✅ **恢复**：改 URL 为 /fgwzwgk/2024zcwj/ 静态列表 |
| bjhd_policy | 海淀区政府 | static | ❌ | — | 404 |

#### B. 人事变动与要闻

| source_id | 名称 | 方法 | 启用 | 条目数 | 详情页 |
|-----------|------|------|------|--------|--------|
| beijing_ywdt | 首都之窗-要闻 | static | ✅ | 0* | ✅ |
| bjd_news | 北京日报 | static | ❌ | — | 布局复杂 |
| bjrd_renshi | 北京市人大常委会 | static | ✅ | 1 | ✅ |
| beijing_rsrm | 首都之窗-人事任免 | static | ❌ | — | URL 404 |

> * beijing_ywdt: 0 条是因为当前首页要闻标题不含 AI/教育/科技关键词。

### 详细状态：industry (对产业) — 6/10 启用 + 1 Twitter

5 启用源配置 detail_selectors，1 RSS 自带正文。

| source_id | 名称 | 方法 | 启用 | 条目数 | 详情页 |
|-----------|------|------|------|--------|--------|
| 36kr_news | 36氪-快讯 | static | ✅ | 3 | 部分 (SSR 有效, CSR 无) |
| huxiu_news | 虎嗅 | static | ❌ | — | WAF 反爬 |
| tmtpost_news | 钛媒体 | rss | ✅ | 3 | RSS 自带 |
| jiemian_tech | 界面新闻-科技 | static | ✅ | 3 | ✅ `div.article-content` |
| thepaper_tech | 澎湃新闻-科技 | static | ❌ | — | Next.js SPA |
| iyiou_ai | 亿欧-AI | static | ❌ | — | 空壳页面 |
| chinaventure_news | 投中网 | static | ✅ | 8 | ✅ `div.article_slice_pc` |
| 36kr_investment | 36氪-融资频道 | static | ❌ | — | URL 已下线 |
| cyzone_news | 创业邦 | rss | ✅ | — | RSS 自带 **新增** AI 创投报道 |
| caict_news | 中国信通院-动态 | static | ✅ | — | — **新增** 产业报告/AI 白皮书 |

### 详细状态：talent (对人才) — 4/7 启用 + 1 Twitter

3 启用源配置 detail_selectors。

| source_id | 名称 | 方法 | 启用 | 条目数 | 详情页 |
|-----------|------|------|------|--------|--------|
| csrankings | CSRankings | static | ❌ | — | React SPA |
| semantic_scholar_ai | Semantic Scholar | API | ✅ | 0† | API 自带 |
| nature_index | Nature Index | static | ✅ | 4 | ✅ `div.c-article-body` |
| aminer_ai | AMiner-AI学者 | static | ❌ | — | JS SPA |
| nsfc_talent | NSFC杰青/优青公示 | static | ❌ | — | URL 404 |
| moe_talent | 教育部人才计划公示 | static | ✅ | 6 | ✅ `div.TRS_Editor` |
| wrsa_talent | 欧美同学会 | static | ✅ | 2 | ✅ `#Content` |

> † semantic_scholar_ai 使用自定义 API Parser，因 429 限速偶尔失败，定时任务自动重试。

### 详细状态：events (对日程) — 4/6 启用

| source_id | 名称 | 方法 | 启用 | 条目数 | 说明 |
|-----------|------|------|------|--------|------|
| aideadlines | AI Conference Deadlines | dynamic | ✅ | 192 | 全量 AI 会议 |
| wikicfp | WikiCFP-AI | static | ✅ | 20 | AI 会议 CFP |
| ccf_focus | CCF 焦点 | static | ✅ | — | **新增** 国内计算机学会活动 |
| caai_news | CAAI 新闻 | static | ✅ | — | **新增** 中国人工智能学会 |
| huodongxing | 活动行-人工智能 | static | ❌ | — | CAPTCHA/反爬 |
| meeting_edu | 中国学术会议在线 | static | ❌ | — | 站点无法连接 |

---

## 四、运行方式

```bash
# 测试单个源（不写数据库，输出 JSON 到 data/raw/）
python scripts/run_single_crawl.py --source pku_news --no-db

# 批量运行所有启用信源（按维度汇总报告）
python scripts/run_all_crawl.py

# 只运行某个维度
python scripts/run_all_crawl.py --dimension technology

# 业务智能加工
python scripts/process_policy_intel.py
python scripts/process_personnel_intel.py

# 重新生成数据索引
python scripts/generate_index.py

# 启动完整服务（含调度器）
uvicorn app.main:app --reload
```
