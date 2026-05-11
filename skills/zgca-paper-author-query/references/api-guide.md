# Papers and OpenReview Authors API Guide

This guide lets an agent query ZGCA/OpenClaw paper records and OpenReview author profiles through HTTP APIs.

## Base URL

Default:

```text
BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
```

Use the caller-provided `BASE_URL` when available. If a deployment provides another public or internal API address, replace only the base URL. Endpoint paths stay the same.

## Endpoint Summary

| Purpose | Method | Path |
| --- | --- | --- |
| List papers | `GET` | `/api/papers` |
| Paper detail | `GET` | `/api/papers/{paper_id}` |
| List OpenReview author profiles | `GET` | `/api/openreview-authors` |
| OpenReview author detail | `GET` | `/api/openreview-authors/{profile_id}` |

No authentication is currently documented for these endpoints.

## `/api/papers`

Lists paper records from the `papers` table. Use this first for paper, venue, year, institution, title, DOI, source, and author-list questions.

### Query Parameters

| Parameter | Type | Meaning |
| --- | --- | --- |
| `q` | string | Fuzzy search in paper `title` and `abstract`. |
| `doi` | string | Exact DOI match after DOI normalization. |
| `source_type` | string | Exact source type filter. |
| `source_name` | string | Exact source name filter. |
| `source_id` | string | Exact source ID filter. |
| `venue` | string | Exact venue filter, such as `ICLR`, `ICML`, `NeurIPS`, `CVPR`. |
| `venue_year` | integer | Conference or publication venue year. |
| `date_from` | string | Publication date lower bound, ISO date or datetime. |
| `date_to` | string | Publication date upper bound, ISO date or datetime. |
| `affiliation` | string | Fuzzy text match over the paper `affiliations` JSONB field. Use for institution queries. |
| `has_abstract` | boolean | `true` only papers with abstracts; `false` only papers without abstracts. |
| `page` | integer | Page number, starts at `1`. |
| `page_size` | integer | Items per page, `1..100`. Default `20`. |
| `sort_by` | string | `publication_date`, `updated_at`, `ingested_at`, or `title`. |
| `order` | string | `asc` or `desc`. Default `desc`. |

### Response Shape

```json
{
  "items": [
    {
      "paper_id": "openreview:abc123",
      "canonical_uid": "openreview:abc123",
      "doi": null,
      "title": "Paper title",
      "abstract": "Abstract text",
      "publication_date": "2026-05-01T00:00:00+00:00",
      "authors": ["Alice Zhang", "Bob Li"],
      "affiliations": [
        {
          "author_order": 1,
          "author_name": "Alice Zhang",
          "affiliation": "Example University"
        }
      ],
      "source": {
        "type": "raw_official",
        "name": "OpenReview",
        "source_id": "openreview_iclr_2026"
      },
      "detail_url": "https://openreview.net/forum?id=abc123",
      "pdf_url": "https://openreview.net/pdf?id=abc123",
      "venue": "ICLR",
      "venue_year": 2026,
      "track": "Main Conference",
      "ingested_at": "2026-05-01T00:00:00+00:00",
      "updated_at": "2026-05-01T00:00:00+00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### Examples

Search ICLR 2026 papers from a specified institution:

```bash
BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
curl -G "$BASE_URL/api/papers" \
  --data-urlencode "venue=ICLR" \
  --data-urlencode "venue_year=2026" \
  --data-urlencode "affiliation=清华大学" \
  --data-urlencode "page=1" \
  --data-urlencode "page_size=20"
```

Search papers by keyword and require abstracts:

```bash
BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
curl -G "$BASE_URL/api/papers" \
  --data-urlencode "q=agent evaluation" \
  --data-urlencode "has_abstract=true" \
  --data-urlencode "sort_by=publication_date" \
  --data-urlencode "order=desc"
```

Get paper detail:

```bash
BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
curl "$BASE_URL/api/papers/openreview%3Aabc123"
```

Path parameters must be URL encoded. For example, `openreview:abc123` becomes `openreview%3Aabc123`.

## `/api/openreview-authors`

Lists OpenReview author profile records. Use this only when the user asks for author profile, institution, email, homepage, career, education, keywords, or publication-count information.

### Query Parameters

| Parameter | Type | Meaning |
| --- | --- | --- |
| `q` | string | Fuzzy search over `profile_id`, `preferred_name`, `university`, `department`, and `keywords`. |
| `university` | string | Fuzzy institution filter. |
| `department` | string | Fuzzy department filter. |
| `crawl_status` | string | Exact crawl status, usually `success`. |
| `min_publication_count` | integer | Minimum OpenReview publication count. |
| `page` | integer | Page number, starts at `1`. |
| `page_size` | integer | Items per page, `1..100`. Default `20`. |
| `sort_by` | string | `publication_count`, `updated_at`, or `preferred_name`. |
| `order` | string | `asc` or `desc`. Default `desc`. |

### Response Fields

Important fields:

| Field | Meaning |
| --- | --- |
| `profile_id` | OpenReview profile ID, such as `~Alice_Zhang1`. |
| `profile_url` | OpenReview profile URL. |
| `preferred_name` | Preferred author name. |
| `preferred_email` / `emails` | Email fields when available. Do not expose unless user asks for contact info. |
| `university` / `department` / `position` | Current profile affiliation fields. |
| `homepage_url`, `google_scholar_url`, `dblp_url`, `orcid` | External academic/profile links when present. |
| `keywords` | OpenReview profile keywords. |
| `career_history`, `education`, `expertise` | Profile enrichment JSON. |
| `publications` | OpenReview publication-note summaries. |
| `publication_count` | Count of OpenReview publication records in this profile. |
| `crawl_status`, `crawl_error` | Profile crawl status. |

### Examples

Search author profiles by name:

```bash
BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
curl -G "$BASE_URL/api/openreview-authors" \
  --data-urlencode "q=Moncef Gabbouj" \
  --data-urlencode "page=1" \
  --data-urlencode "page_size=5"
```

Search high-publication authors from an institution:

```bash
BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
curl -G "$BASE_URL/api/openreview-authors" \
  --data-urlencode "university=University of Oxford" \
  --data-urlencode "min_publication_count=20" \
  --data-urlencode "sort_by=publication_count" \
  --data-urlencode "order=desc"
```

Get one OpenReview profile:

```bash
BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
curl "$BASE_URL/api/openreview-authors/~Moncef_Gabbouj1"
```

If a `profile_id` contains reserved URL characters, URL encode it.

## Intent Mapping

| User asks | API plan |
| --- | --- |
| “查清华 ICLR 2026 论文” | `/api/papers?venue=ICLR&venue_year=2026&affiliation=清华` |
| “查某会议论文作者” | `/api/papers?venue=...`; extract `authors` and `affiliations`. |
| “查某机构某会议论文和作者信息” | `/api/papers` with `venue`, optional `venue_year`, `affiliation`; render paper list plus author/affiliation table. |
| “查某作者 OpenReview 画像” | `/api/openreview-authors?q=<author>`; if unique, detail by `profile_id`. |
| “查某机构 OpenReview 作者” | `/api/openreview-authors?university=<institution>` |
| “查作者邮箱/主页/经历” | `/api/openreview-authors` then `/api/openreview-authors/{profile_id}`. |
| “查 DOI 论文” | `/api/papers?doi=<doi>` |
| “查包含某关键词的论文” | `/api/papers?q=<keyword>` |

## Recommended Multi-Step Patterns

### Institution + Conference Paper Report

1. Call `/api/papers` with `venue`, optional `venue_year`, and `affiliation`.
2. If `total > page_size` and the user asked for complete coverage, paginate until enough results or until a reasonable cap.
3. For each paper, extract:
   - `title`
   - `venue`, `venue_year`, `track`
   - `authors`
   - `affiliations`
   - `detail_url`, `pdf_url`
4. Render a paper-first answer. Do not claim author profile details unless `/api/openreview-authors` was called.

### Author Enrichment From Paper Results

1. First call `/api/papers`.
2. Select only relevant author names from returned `authors` and `affiliations`.
3. For each important author, call `/api/openreview-authors?q=<author_name>`.
4. If multiple profiles match, disambiguate by `university`, `department`, and publication evidence. If still ambiguous, return candidates instead of forcing one.
5. Call profile detail only for unique or top candidates.

Request budget recommendation:

| Endpoint | Default cap |
| --- | ---: |
| `/api/papers` | 1-3 pages |
| `/api/papers/{paper_id}` | only when user asks for detail |
| `/api/openreview-authors` | top 3-10 author names |
| `/api/openreview-authors/{profile_id}` | top 1-3 profiles |

## Capability Boundaries

Supported:

- Paper list/detail from the `papers` table.
- Filtering papers by conference venue, venue year, affiliation text, title/abstract keyword, DOI, source, date, and abstract availability.
- Paper author names and paper-level affiliation mappings through `/api/papers`.
- OpenReview author profile list/detail through `/api/openreview-authors`.
- OpenReview author filters by name/keyword, university, department, crawl status, and minimum publication count.

Partially supported:

- Institution matching is text-based. It can miss aliases such as `Tsinghua University` vs `清华大学`.
- Paper-author profile joining is not automatic. The agent must query papers first, then search OpenReview authors by name/institution.
- Same-name author disambiguation is approximate unless profile IDs or strong affiliation evidence are available.
- Email/contact output depends on profile data availability and should only be shown when requested.

Not directly supported:

- Citation ranking, h-index ranking, or Google Scholar metrics through these endpoints.
- Full-text PDF parsing.
- Guaranteed complete author affiliation for every paper.
- Cross-source author identity graph beyond OpenReview profile records.
- Automatic “best talent” scoring unless the agent explains its heuristic.

## Output Template

Use Chinese by default.

```text
查询范围：{institution/venue/year/keyword}，命中 {total} 篇论文。

1. {paper_title}
   - 会议/年份：{venue} {venue_year}，{track}
   - 作者：{authors}
   - 机构证据：{author_name -> affiliation}
   - 链接：{detail_url}；PDF：{pdf_url}

作者画像补充（如调用了 /api/openreview-authors）：
- {preferred_name}：{university} / {department} / {position}
  OpenReview：{profile_url}
  关键词：{keywords}
  OpenReview 发表数：{publication_count}

能力边界：{only when needed}
后续可精化参数：{venue_year / affiliation alias / min_publication_count / page_size}
```

## Failure Handling

API unavailable:

```text
当前论文/作者 API 暂时不可用：{error_summary}。为避免误导，我不使用本地文件或编造结果。请稍后重试或确认 `BASE_URL` 对应服务是否可访问。
```

No results:

```text
当前参数未命中论文/作者记录。建议尝试：放宽 `venue_year`、换用中英文机构别名、删除 `has_abstract`、或先只用 `venue`/`q` 查询。
```

Unsupported request:

```text
当前 papers/openreview-authors API 暂不直接支持：{unsupported_parts}。我可以先返回 API 支持范围内的论文、作者名单和 OpenReview 画像，并明确标注缺口。
```
