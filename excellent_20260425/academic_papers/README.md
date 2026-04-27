# 学术论文作者爬虫

抓取 AI/LLM/Agent 相关顶会论文的主要作者信息。

## 数据来源

本爬虫使用以下 API 获取数据：

### 1. Semantic Scholar API
- **用途**: 搜索 LLM/Agent 相关论文，获取作者信息和引用统计
- **API 文档**: https://api.semanticscholar.org
- **端点**:
  - `/paper/search` - 论文搜索
  - `/author/{id}` - 作者详细信息
- **优势**: 
  - 免费使用，无需 API Key
  - 提供完整的引用统计
  - 包含作者 h-index 信息

### 2. OpenReview API
- **用途**: 获取 ICLR、NeurIPS 等会议的论文和作者信息
- **API 文档**: https://openreview.net/api
- **端点**:
  - `/notes` - 会议论文列表
- **优势**:
  - 包含最新的会议投稿
  - 提供 Open Access 论文

### 3. DBLP API
- **用途**: 查询作者发表记录
- **API 文档**: https://dblp.org/api
- **端点**:
  - `/search/author/api` - 作者搜索
  - `/pid/{id}.json` - 作者发布记录
- **优势**:
  - 权威的计算机科学文献数据库
  - 完整的作者发布历史

## 筛选条件

### 目标会议
- ICML (International Conference on Machine Learning)
- ICLR (International Conference on Learning Representations)
- NeurIPS (Neural Information Processing Systems)
- AAAI (AAAI Conference on Artificial Intelligence)
- ACL (Annual Meeting of the Association for Computational Linguistics)
- EMNLP (Empirical Methods in Natural Language Processing)
- CVPR (Conference on Computer Vision and Pattern Recognition)
- ICCV (International Conference on Computer Vision)

### 关键词
- large language model
- LLM
- agent
- autonomous agent
- language model
- foundation model
- GPT
- transformer

## 使用方法

### 环境要求
```bash
pip install requests
```

### 运行爬虫
```bash
python crawler.py
```

### 输出格式
结果保存在 `results.json`，格式如下：

```json
{
  "source": "academic_papers",
  "crawl_time": "2026-04-25T06:44:00Z",
  "total_authors": 150,
  "total_papers": 500,
  "top_authors_count": 200,
  "authors": [
    {
      "name": "作者名",
      "affiliations": ["机构1", "机构2"],
      "papers": [
        {
          "title": "论文标题",
          "venue": "会议名",
          "year": 2024,
          "citations": 1000
        }
      ],
      "total_papers": 10,
      "total_citations": 5000,
      "h_index": 25
    }
  ]
}
```

## 字段说明

| 字段 | 说明 |
|------|------|
| `name` | 作者姓名 |
| `affiliations` | 所属机构列表 |
| `papers` | 作者在目标会议的相关论文列表 |
| `total_papers` | 相关论文总数 |
| `total_citations` | 总引用数 |
| `h_index` | 计算 H-index（基于相关论文） |

## 速率限制

为遵守 API 使用规范，爬虫内置了速率限制：
- Semantic Scholar: 每次请求间隔 1 秒
- OpenReview: 每次请求间隔 2 秒
- DBLP: 每次请求间隔 1 秒

## 注意事项

1. **API 限制**: Semantic Scholar 无需 API Key，但建议在大规模爬取时申请 API Key 以提高限制
2. **数据完整性**: 由于 API 限制，爬虫只抓取 Top 200 作者和限制数量的论文
3. **更新频率**: 建议每周或每月运行一次以获取最新数据
4. **引用数**: 引用数可能不是实时的，Semantic Scholar 每天更新

## 扩展建议

1. 添加更多关键词以扩大覆盖范围
2. 使用 Semantic Scholar API Key 提高请求限制
3. 添加 arXiv API 获取预印本论文
4. 集成 Google Scholar（需处理反爬虫）

## 许可证

数据仅供学术研究使用，请遵守各 API 的使用条款。

## 联系方式

如有问题或建议，请提交 Issue。
