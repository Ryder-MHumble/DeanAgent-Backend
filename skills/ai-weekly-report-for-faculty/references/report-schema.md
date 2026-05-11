# Faculty Weekly Report Schema

Build a JSON file and pass it to `scripts/render_faculty_report.py`.

## Minimal Schema

```json
{
  "title": "人工智能信息速递",
  "issue_label": "2026年4月第4周",
  "volume_label": "Vol. I · No. 01 · 2026",
  "date_range_label": "2026.04.21 — 2026.04.27",
  "week_start_label": "四月 二十一日",
  "week_end_label": "四月 二十七日",
  "publisher": "北京中关村学院 · 学工部",
  "editorial_note": "本期速递依托情报引擎 API，并以联网检索作为低优先级补充...",
  "summary": [
    {"label": "AI 重磅事件", "desc": "一句话要情"},
    {"label": "科 技 产 业", "desc": "一句话要情"},
    {"label": "三 全 育 人", "desc": "一句话要情"},
    {"label": "教 育 政 策", "desc": "一句话要情"}
  ],
  "sections": [
    {
      "key": "ai_frontier",
      "number": "I",
      "tag": "AI Frontier",
      "title": "人工智能最新热点",
      "subtitle": "2026.04.21 — 2026.04.27 · 全球及国内 AI 领域重大动态 · TOP 5",
      "items": [
        {
          "title": "文章标题",
          "url": "https://example.com/article",
          "source_names": ["OpenAI Blog"],
          "published_at": "2026-04-24",
          "body": ["1-2段专业摘要，每段不超过120字。"],
          "why_it_matters": "对教学科研或学院工作的参考价值。",
          "tags": ["大模型", "教学科研"],
          "provenance": "api",
          "verification": {"status": "verified", "checked_url": "https://example.com/article"}
        }
      ]
    }
  ],
  "data_note": "API 为第一优先级数据源；联网搜索仅作补充；404/不可访问链接已删除。"
}
```

## Standard Sections

Use these five sections unless the user explicitly changes the structure:

1. `人工智能最新热点`
2. `科技产业动态`
3. `三全育人实践`
4. `友院专栏`
5. `教育政策追踪`

## Field Rules

- `provenance`: `api` or `web`.
- `verification.status`: `verified`, `limited`, or `removed`. Do not render removed items.
- `source_names`: human-readable original source names, not source IDs.
- `body`: factual synthesis from API detail/content or verified web page content.
- `why_it_matters`: must be practical and faculty-facing; avoid promotional wording.
- `tags`: 2-5 concise tags.
