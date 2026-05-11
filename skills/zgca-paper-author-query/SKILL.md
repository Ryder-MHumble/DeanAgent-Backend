---
name: zgca-paper-author-query
description: Use when users ask to query ZGCA/OpenClaw papers, conference papers, institutional publications, paper authors, author affiliations, or OpenReview author profiles through the papers and openreview-authors APIs.
---

# ZGCA Paper Author Query

## Core Rules

- Only use the HTTP APIs documented in `references/api-guide.md` and the API responses.
- Do not read local source code, database tables, crawler outputs, or exported files to answer user queries.
- Use caller-provided `BASE_URL`; local backend fallback is `http://127.0.0.1:8001`.
- If deployment provides another public or internal API address, replace only the base URL. Endpoint paths stay the same.
- Use URL encoding for all Chinese query parameters. In shell examples prefer `curl -G --data-urlencode`.
- Do not invent paper titles, author names, affiliations, profile links, or publication counts.
- If an endpoint is unavailable, report the API failure instead of switching to local files or public web search.

## When To Use

Use this skill for:

- 查询某会议、年份、机构、关键词下的论文。
- 查询某篇论文详情、作者列表、作者机构映射。
- 查询某机构在某会议上的论文与作者信息。
- 查询 OpenReview 作者画像、profile、邮箱、机构、关键词、发表记录。
- 需要把自然语言问题转成 `/api/papers` 或 `/api/openreview-authors` 参数。

Do not use this skill for:

- 学者档案、导师、院士、潜在招募等非论文表查询，优先用 `scholar-skill`。
- 学生论文业务流、学生合规状态，优先用 `student-skill`。
- 外部公网论文库检索，除非用户明确要求联网补充。

## Workflow

1. Read `references/api-guide.md`.
2. Classify intent:
   - `paper_list`: list papers from `/api/papers`.
   - `paper_detail`: get one paper from `/api/papers/{paper_id}`.
   - `author_profile_list`: list OpenReview authors from `/api/openreview-authors`.
   - `author_profile_detail`: get one OpenReview profile from `/api/openreview-authors/{profile_id}`.
   - `paper_author_report`: combine paper list results with optional OpenReview author profile lookups.
3. Start with the narrowest paper query. Use `page_size=20` by default and paginate only if needed.
4. For institutional conference questions, query papers with `venue`, optional `venue_year`, and `affiliation`; then extract `authors` and `affiliations` from returned papers.
5. Only call `/api/openreview-authors` when the user asks for author profiles, emails, career/education, keywords, or profile URLs.
6. Return concise Chinese results with API capability gaps clearly stated.

## Output Style

- Start with query scope and matched count.
- For each paper, include `title`, `venue`, `venue_year`, `publication_date`, `authors`, affiliation evidence, and `detail_url`/`pdf_url` if present.
- For author profiles, include `preferred_name`, `profile_url`, `university`, `department`, `position`, `keywords`, and `publication_count`.
- If no results: state no matches and suggest concrete parameter refinements.
- If partially supported: explain which part was supported by current APIs and which part is not directly supported.
