---
name: ai-weekly-report-for-faculty
description: Use when creating AI信息速递、全院教师版AI周报、faculty AI weekly reports, or producing HTML/PDF briefing documents from intelligence-engine API data plus lower-priority verified web sources.
---

# AI Weekly Report for Faculty

## Core Principle

Generate a rigorous faculty-facing AI weekly report as HTML and PDF. The intelligence API is the primary source; web search is secondary and must pass source/date/URL verification before use.

## Required Workflow

1. **Set scope**
   - Use caller-provided `BASE_URL`; local backend fallback is `http://127.0.0.1:8001`.
   - If deployment provides another public or internal API address, replace only the base URL. Endpoint paths stay the same.
   - Resolve exact `week_start` and `week_end`; never leave relative dates in output.

2. **Fetch API data first**
   - Use `GET /api/sources/items` with A/B/C source groups from `references/api-contract.md`.
   - Page through results (`page_size=100`) until complete or user-requested cap.
   - Fetch selected article detail with `GET /api/articles/{article_id}` before summarizing.

3. **Use web search only as supplement**
   - Use web search when an expected section has fewer than 3 usable API items, the user asks for a topic missing from API data, or API is unavailable.
   - Web items rank below API items.
   - Every web item must pass the verification rules in `references/api-contract.md`.
   - Delete any item whose canonical URL returns `404`, `410`, or an inaccessible error page.

4. **Synthesize report content**
   - Style: 严谨、专业、克制，不夸张，不编造。
   - Each included item must have `title`, `url`, `source_names`, `published_at`, `summary`, and `why_it_matters`.
   - Use the section plan and JSON schema in `references/report-schema.md`.

5. **Render deliverables**
   - Build `report.json` following `references/report-schema.md`.
   - Run:
     ```bash
     python3 skills/ai-weekly-report-for-faculty/scripts/render_faculty_report.py report.json --out-dir output/faculty-weekly --pdf
     ```
   - If Playwright is unavailable, still generate HTML and tell the user PDF conversion is blocked by missing dependency.
   - Return the generated `.html` and `.pdf` paths to the user.

## Output Requirements

- Deliver both HTML and PDF when PDF rendering is available.
- HTML must follow the newspaper-style template inspired by `AI-信息速递-2026年4月第4周-全院教师版.html`: masthead, editor note, weekly summary grid, five sections, article cards, source badges, tags, footer.
- Every article title in HTML must link to the verified source URL.
- Include a short “数据与校验说明” footer: API primary, web supplemental, inaccessible URLs removed.

## Failure Handling

- API unavailable:
  ```text
  当前情报引擎接口暂时不可用：{error_summary}。我将仅在用户允许时使用联网搜索补充，并明确标注低优先级外部来源。
  ```
- PDF conversion unavailable:
  ```text
  HTML 已生成，但 PDF 转换失败：{error_summary}。请在具备 Playwright/Chromium 的环境重试转换命令。
  ```
- Insufficient verified data:
  ```text
  本周期部分栏目可用信息不足。已删除 404/不可访问链接，不使用无法核验的信息。
  ```
