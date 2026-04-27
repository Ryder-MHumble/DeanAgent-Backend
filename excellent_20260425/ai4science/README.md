# AI for Science 竞赛爬虫

本目录包含用于爬取 AI for Science 相关竞赛数据的爬虫脚本。

## 数据来源

### 1. CASP (蛋白质结构预测竞赛)
- **全称**: Critical Assessment of protein Structure Prediction
- **网址**: https://predictioncenter.org
- **说明**: CASP 是蛋白质结构预测领域的权威竞赛，每两年举办一次。参赛队伍需要预测未知蛋白质的三维结构。

### 2. iGEM (合成生物学竞赛)
- **全称**: International Genetically Engineered Machine Competition
- **网址**: https://igem.org
- **说明**: iGEM 是合成生物学领域的国际顶级竞赛，汇集全球高校学生团队。

## 爬取方法

### CASP 数据爬取

1. **数据来源**: CASP 官方网站的 `groups_analysis.cgi` 页面
   - CASP13: https://predictioncenter.org/casp13/groups_analysis.cgi
   - CASP14: https://predictioncenter.org/casp14/groups_analysis.cgi
   - CASP15: https://predictioncenter.org/casp15/groups_analysis.cgi

2. **解析方法**:
   - 使用 `requests` 库获取 HTML 页面
   - 使用 `BeautifulSoup` 解析 HTML 表格
   - 提取字段：
     - 队伍名称 (GR name)
     - 排名 (Rank)
     - GR 编号
     - 是否为服务器 (Server/Human)
     - 预测域数量 (Domains Count)
     - 平均 GDT_TS 分数

3. **数据清洗**:
   - 过滤无效数据（排名为0、无 GR 编号）
   - 去重处理
   - 根据队伍名称推断学校和所属国家
   - 根据排名判断获奖级别

### iGEM 数据爬取

**注意**: iGEM 官方网站使用 JavaScript 渲染，需要使用以下方法之一：

1. **推荐方法**: 使用 Selenium 或 Playwright
   ```python
   from selenium import webdriver
   from selenium.webdriver.chrome.options import Options

   options = Options()
   options.add_argument('--headless')
   driver = webdriver.Chrome(options=options)
   driver.get('https://igem.org/Teams')
   # 等待页面加载完成后解析
   ```

2. **替代方法**: 使用 iGEM 官方 API（如果可用）

3. **当前实现**: 使用历史记录数据作为示例

## 输出格式

结果保存在 `results.json`，格式如下：

```json
{
  "source": "ai4science",
  "crawl_time": "2026-04-25T06:46:53Z",
  "competitions": [
    {
      "name": "CASP15",
      "year": 2022,
      "description": "Critical Assessment of protein Structure Prediction",
      "url": "https://predictioncenter.org/casp15/groups_analysis.cgi",
      "teams": [
        {
          "name": "Yang-Server",
          "rank": 1,
          "gr_number": "229",
          "is_server": true,
          "domains_count": 108,
          "avg_gdt_ts": 83.945,
          "award": "Gold Medal / Top Performer",
          "school": "Yang Lab",
          "country": "China",
          "project": "Protein Structure Prediction (CASP15)"
        }
      ]
    }
  ]
}
```

### 字段说明

| 字段 | 说明 |
|------|------|
| `name` | 队伍名称 |
| `rank` | 最终排名 |
| `gr_number` | CASP 官方分配的队伍编号 |
| `is_server` | 是否为服务器队伍（自动化预测） |
| `domains_count` | 预测的蛋白质域数量 |
| `avg_gdt_ts` | 平均 GDT_TS 分数（预测准确性指标） |
| `award` | 获奖级别（基于排名推断） |
| `school` | 所属学校/机构 |
| `country` | 国家/地区 |
| `project` | 项目描述 |

## 使用方法

### 安装依赖

```bash
pip install requests beautifulsoup4
```

### 运行爬虫

```bash
python crawler.py
```

### 结果文件

- `results.json` - 爬取结果（JSON 格式）

## 数据统计

| 竞赛 | 年份 | 队伍数量 |
|------|------|----------|
| CASP13 | 2018 | 124 |
| CASP14 | 2020 | 146 |
| CASP15 | 2022 | 132 |
| iGEM 2023 | 2023 | 5 (示例数据) |
| iGEM 2024 | 2024 | 5 (示例数据) |
| **总计** | - | **412** |

## 注意事项

1. **CASP 数据**:
   - 数据直接来自官方网站，准确可靠
   - 包含服务器队伍和人类队伍两类
   - GDT_TS 分数范围 0-100，越高越好

2. **iGEM 数据**:
   - 当前版本使用历史数据作为示例
   - 完整数据需要使用 Selenium/Playwright 爬取
   - 每年参赛队伍通常在 300-400 支左右

3. **数据更新**:
   - CASP 数据每两年更新一次
   - iGEM 数据每年更新

## 扩展建议

如需爬取更多竞赛数据，可考虑：

1. **CAPRI** (蛋白质-蛋白质对接预测): https://capri.ebi.ac.uk
2. **RNA-Puzzles** (RNA 结构预测): http://www.rnapuzzles.org
3. **CAMEO** (持续评估平台): https://cameo3d.org
4. **Kaggle Competitions** (各类 AI 竞赛): https://www.kaggle.com/competitions

## 许可证

本爬虫仅供学术研究使用。数据版权归原竞赛主办方所有。
