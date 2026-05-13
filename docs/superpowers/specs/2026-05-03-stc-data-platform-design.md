# StC Data Platform — Design Spec
**Date:** 2026-05-03  
**Client:** SubjectToClimate (StC) — educational nonprofit  
**Status:** Approved

---

## Overview

An internal data analytics platform that aggregates search and web analytics data from three sources (GA4, Google Search Console, Meilisearch) into a single Supabase PostgreSQL database. Non-technical staff can ask plain-English questions via a simple web UI; Claude AI converts questions to SQL and formats results back into plain-English answers.

---

## Business Questions This Platform Answers

- Are most of our super users looking for elementary (grade 3–5) materials? What are they searching for?
- What are the most popular pathways to and through our site?
- Where do popular users drop off? At what friction point could we intervene?
- Is anyone using this teacher guide?
- What resources are evergreen (popular all year round)?
- What content gaps do we have? (searches with no results, high-impression GSC queries with no matching content)

---

## Architecture

```
GA4 API    Google Search Console API    Meilisearch API
    │                  │                       │
    ▼                  ▼                       ▼
sync_ga4.py       sync_gsc.py       sync_meilisearch.py
    │                  │                       │
    └──────────────────┴───────────────────────┘
                       │
                       ▼
              Supabase (PostgreSQL)
           6 tables, composite unique keys
                       │
              ┌────────┴────────┐
              ▼                 ▼
         Claude API        GitHub Actions
         (Haiku)           (daily cron 06:00 UTC)
         SQL gen +
         answer format
              │
              ▼
       Static Web UI
       (index.html / app.js)
```

**Key decisions:**
- Three independent sync scripts — one failing does not block the others
- GitHub Actions cron — no extra infrastructure, free tier sufficient
- Claude Haiku — fastest/cheapest model; schema is small so context is minimal
- Static frontend — no backend server, no login, internal tool for trusted team
- Read-only Postgres role for AI query execution — no write access possible

---

## Database Schema

All tables use composite unique keys to make daily upserts safe and idempotent. Old data is never deleted; new rows accumulate daily.

### `ga4_page_metrics`
Daily page performance from GA4.

| Column | Type | Notes |
|---|---|---|
| `date` | date | |
| `page_path` | text | e.g. `/resources/penguins` |
| `landing_page` | text | session entry page |
| `source_medium` | text | e.g. `google / organic` |
| `screen_class` | text | PWA/app tracking |
| `sessions` | integer | |
| `total_users` | integer | |
| `new_users` | integer | |
| `engaged_sessions` | integer | |
| `avg_engagement_time_sec` | numeric | |
| `bounce_rate` | numeric | |
| `screenpage_views` | integer | |

**Unique key:** `(date, page_path, source_medium, landing_page, screen_class)`

---

### `gsc_queries`
Search Console query-level performance.

| Column | Type | Notes |
|---|---|---|
| `date` | date | |
| `query` | text | Google search term |
| `page` | text | landing URL |
| `country` | text | ISO country code |
| `device` | text | DESKTOP / MOBILE / TABLET |
| `clicks` | integer | |
| `impressions` | integer | |
| `ctr` | numeric | |
| `position` | numeric | average ranking |

**Unique key:** `(date, query, page, country, device)`

---

### `gsc_pages`
Search Console page-level aggregates.

| Column | Type | Notes |
|---|---|---|
| `date` | date | |
| `page` | text | full URL |
| `clicks` | integer | |
| `impressions` | integer | |
| `ctr` | numeric | |
| `position` | numeric | |

**Unique key:** `(date, page)`

---

### `ms_top_searches`
Meilisearch top queried terms.

| Column | Type | Notes |
|---|---|---|
| `date` | date | sync date = previous day's data |
| `query_term` | text | |
| `search_count` | integer | |

**Unique key:** `(date, query_term)`

---

### `ms_no_results`
Meilisearch queries that returned no results.

| Column | Type | Notes |
|---|---|---|
| `date` | date | |
| `query_term` | text | |
| `search_count` | integer | |

**Unique key:** `(date, query_term)`

---

### `ms_countries`
Meilisearch searches by country.

| Column | Type | Notes |
|---|---|---|
| `date` | date | |
| `country_code` | text | ISO code e.g. `US`, `CA` |
| `search_count` | integer | |

**Unique key:** `(date, country_code)`

---

### Cross-source join keys

- `gsc_queries.query` ↔ `ms_top_searches.query_term` — content gap analysis (same term in both = high-intent topic; in ms_no_results only = content gap)
- `gsc_queries.page` ↔ `ga4_page_metrics.page_path` — connects organic traffic to on-site behavior per page
- Claude handles fuzzy query matching via `LOWER()` / `ILIKE` in generated SQL

---

## Sync Scripts

**Tech stack:** Python  
**Auth:** Google service account (`ga4-credentials.json`) for GA4 + GSC; `MEILISEARCH_API_KEY` for Meilisearch

### `sync_ga4.py`
- GA4 Data API v1
- Dimensions: `date`, `pagePath`, `landingPage`, `sessionSourceMedium`, `screenClass`
- Metrics: `sessions`, `totalUsers`, `newUsers`, `engagedSessions`, `userEngagementDuration`, `bounceRate`, `screenPageViews`
- Daily pull: `today - 2 days` (accounts for GA4's 48h processing lag)
- Backfill: loops month-by-month back 12 months, respects API quota
- Upserts into `ga4_page_metrics`

### `sync_gsc.py`
- Google Search Console API v3
- Two pulls per run:
  - Query-level: `date`, `query`, `page`, `country`, `device` → `gsc_queries`
  - Page-level: `date`, `page` → `gsc_pages`
- Daily pull: `today - 3 days` (GSC has a 2–3 day data lag)
- Paginates via `startRow` offset (GSC max 25,000 rows per request)
- Backfill: loops week-by-week back 12 months

### `sync_meilisearch.py`
- Meilisearch Analytics REST API (not CSV — API covers the same data, is programmatic and reliable)
- Three endpoint pulls:
  - `/search-analytics/top-searches` → `ms_top_searches`
  - `/search-analytics/searches-without-results` → `ms_no_results`
  - Country breakdown → `ms_countries`
- Daily pull: yesterday only
- Backfill: loops day-by-day back 90 days (Meilisearch retention limit)

### `daily_sync.yml` (GitHub Actions)
- Schedule: `0 6 * * *` (06:00 UTC daily)
- Runs all three scripts independently; one failure does not block others
- Credentials stored as GitHub Actions Secrets

---

## AI Query Layer

### Flow
1. User submits plain-English question via web UI
2. **Call 1 (SQL gen):** Claude Haiku receives cached system prompt (full schema DDL) + user question → returns SQL string
3. **Safety check:** strip any non-SELECT statement before execution; never execute writes
4. **Execution:** SQL runs via Supabase RPC function `execute_query` under a read-only Postgres role
5. **Call 2 (answer format):** Claude Haiku receives cached system prompt + original question + raw JSON rows → returns plain-English answer

### Prompt caching
- Full schema DDL (all 6 tables) written once as the system prompt with Anthropic cache-control breakpoint
- All subsequent calls reuse the cached schema — reduces latency and token cost significantly for a team asking many questions per day

### Security
```sql
-- Read-only role
CREATE ROLE readonly_ai;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_ai;

-- RPC function (executes under readonly_ai)
CREATE FUNCTION execute_query(sql text)
RETURNS json LANGUAGE plpgsql SECURITY DEFINER AS $$...$$;
```

---

## Frontend

Static HTML/JS — no framework, no build step. Three files:

- `index.html` — structure: text input, Ask button, answer display area
- `style.css` — clean readable styling
- `app.js` — calls the query engine endpoint, renders the plain-English answer

Hosted on GitHub Pages or Supabase Storage (both free). No authentication — internal tool for a trusted team.

---

## Historical Data & Refresh Strategy

| Source | Backfill window | Daily pull offset | Reason |
|---|---|---|---|
| GA4 | 12 months | today - 2 days | 48h processing lag |
| GSC | 12 months | today - 3 days | 2–3 day data lag |
| Meilisearch | 90 days | yesterday | API retention limit |

Cross-source unified queries have a 90-day overlap window (Meilisearch cap). For older data, GA4 and GSC rows exist but Meilisearch columns will be absent — handled gracefully via LEFT JOINs, not INNER JOINs.

---

## Project File Structure

```
stc-data-platform/
├── .env
├── ga4-credentials.json
├── requirements.txt
├── sync/
│   ├── sync_ga4.py
│   ├── sync_gsc.py
│   └── sync_meilisearch.py
├── db/
│   └── schema.sql
├── .github/
│   └── workflows/
│       └── daily_sync.yml
└── app/
    ├── index.html
    ├── style.css
    └── app.js
```

---

## Dependencies

```
google-analytics-data
google-api-python-client
google-auth
supabase
python-dotenv
requests
anthropic
```
