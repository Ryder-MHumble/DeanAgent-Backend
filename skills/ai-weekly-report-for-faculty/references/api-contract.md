# API Contract and Source Priority

## Service

- Base URL: caller-provided `BASE_URL`; local backend fallback is `http://127.0.0.1:8001`
- If deployment provides another public or internal API address, replace only the base URL. Endpoint paths stay the same.
- Health: `GET /api/health`
- Source items: `GET /api/sources/items`
- Article detail: `GET /api/articles/{article_id}`

## `/api/sources/items`

Use `curl -G --data-urlencode` for Chinese query params.

Required params:
- `source_names`: comma-separated source names
- `date_from`: `YYYY-MM-DD`
- `date_to`: `YYYY-MM-DDT23:59:59+00:00`
- `sort_by=published_at`
- `order=desc`
- `page_size=100`
- `page`: start at `1`

Do not pass `keyword` by default. Fetch broadly first, then filter in the agent; this avoids missing items whose titles do not contain the keyword.

## Priority Source Groups

```yaml
A类必选:
  - 教育部-政策法规
  - 北京市教委
  - 中国教育在线-要闻
  - 中国教育报
  - 上海创智学院
  - 深圳河套学院-学院动态
  - 北京智源人工智能研究院(BAAI)-智源社区
  - 清华大学新闻网-最新动态
  - 北京大学新闻网
  - OpenAI Blog
  - Qwen Blog (阿里通义千问)
  - 36氪-AI频道
B类增强:
  - 科技部-信息公开
  - 工信部-新闻发布（部领导活动/司局动态）
  - 北京市科委/中关村管委会
  - 上海人工智能实验室-科研动态
  - 之江实验室
  - 华中科技大学新闻网
  - 天津大学新闻网
  - 复旦大学新闻网
  - Anthropic News
  - Google DeepMind Blog
  - CAAI学会新闻
  - 中国信通院-动态
C类补充:
  - 澎湃新闻-10%公司
  - 钛媒体
  - 投中网
  - AI Conference Deadlines
  - WikiCFP-AI
  - 腾讯混元-最新动态
  - 月之暗面-最新研究
  - Hugging Face Blog
```

## URL Verification

Apply to API and web items before final inclusion.

Delete item if:
- URL returns HTTP `404` or `410`.
- URL resolves to an obvious error page, login wall, CAPTCHA-only page, or empty shell.
- URL cannot be opened after one retry and no alternate canonical URL is available.

Keep but mark `verification.status=limited` only when:
- The item is from API, title/date are present, but detail content is short.
- HTTP method blocks `HEAD` but `GET` returns valid page content.

For web search items:
- Prefer primary sources: official company, university, ministry, journal, conference, or standards body.
- High-impact claims with numbers, policy names, rankings, funding, or release dates need a primary source or two independent credible sources.
- Do not use search-result snippets as facts.
- Publication date must be inside the report week unless the item is explicitly background context.

## Example Requests

```bash
BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
curl -G "$BASE_URL/api/sources/items" \
  --data-urlencode "source_names=教育部-政策法规,北京市教委,中国教育在线-要闻,中国教育报,上海创智学院,深圳河套学院-学院动态,北京智源人工智能研究院(BAAI)-智源社区,清华大学新闻网-最新动态,北京大学新闻网,OpenAI Blog,Qwen Blog (阿里通义千问),36氪-AI频道" \
  --data-urlencode "date_from=$WEEK_START" \
  --data-urlencode "date_to=${WEEK_END}T23:59:59+00:00" \
  --data-urlencode "sort_by=published_at" \
  --data-urlencode "order=desc" \
  --data-urlencode "page_size=100" \
  --data-urlencode "page=1"
```

```bash
BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
curl "$BASE_URL/api/articles/$ARTICLE_ID"
```
