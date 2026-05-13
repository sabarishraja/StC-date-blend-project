# SubjectToClimate — Data Intelligence Platform
**Project:** StC Data Blending V2
**Status:** Operational
**Last Updated:** May 2026

---

## Section 1: For Non-Technical Members

### What is this project?

We built a system that lets anyone on the team ask plain-English questions about SubjectToClimate's website performance and get real answers — instantly, without needing to know how to use Google Analytics, Search Console, or any other tool.

### What can you ask it?

You type a question like you would to a colleague. For example:

- *"What were the top 5 pages by sessions last month?"*
- *"Which Google search queries drove the most clicks to our site this week?"*
- *"What are visitors searching for on our site that returns no results?"*
- *"Which countries are our visitors coming from?"*
- *"Which pages have the highest bounce rate?"*

The system understands the question, pulls the relevant data, and gives you a written summary of the answer.

### Where does the data come from?

Three sources are connected and updated automatically every day:

| Data Source | What it tells us |
|-------------|-----------------|
| **Google Analytics 4 (GA4)** | How people use the website — page visits, session length, bounce rate, where traffic came from |
| **Google Search Console (GSC)** | How the site appears in Google search — what people searched for, how many clicks we got, which pages rank |
| **Meilisearch** | What visitors searched for *on our own site* — top search terms, failed searches with no results, countries |

### How much history do we have?

- **GA4:** 12 months of data
- **Google Search Console:** 16 months of data
- **Meilisearch:** 30 days of data (platform limitation — 90 days requires an enterprise plan)

### How do you use it?

1. Someone on the team opens a terminal and runs one command to start the system
2. Open the `app/index.html` file in any browser
3. Type your question and press Ask
4. Get your answer in seconds

### What happens every day automatically?

A scheduled job runs every morning at 6:00 AM UTC and pulls the previous day's data from all three sources into the database. The system always stays current without anyone needing to do anything.

### What are the current limitations?

- Meilisearch analytics data requires a manual export from their dashboard once a month (their API does not support automated pulls on the current plan)
- The system answers questions about data we have — it cannot predict future trends or access data outside the three connected sources

---

## Section 2: For Technical Members

### Architecture Overview

```
GA4 API  ─┐
GSC API  ──┼──► sync scripts ──► Supabase (PostgreSQL) ──► FastAPI ──► Claude Haiku ──► Web UI
Meilisearch CSV ─┘
```

### Stack

| Component | Technology |
|-----------|-----------|
| Database | Supabase (PostgreSQL) |
| Sync scripts | Python 3.11 |
| Google auth | OAuth2 with refresh token (`token.json`) |
| AI query layer | FastAPI + Anthropic Claude Haiku (`claude-haiku-4-5-20251001`) |
| Frontend | Static HTML/CSS/JS (`app/index.html`) |
| Scheduler | GitHub Actions cron (`.github/workflows/`) |

### Repository Structure

```
.
├── sync/
│   ├── sync_ga4.py              # Pulls GA4 page metrics → Supabase
│   ├── sync_gsc.py              # Pulls GSC search data → Supabase
│   ├── sync_meilisearch.py      # (Legacy) API-based pull — not in use
│   └── load_meilisearch_csv.py  # Loads manually exported Meilisearch CSVs
├── server/
│   └── query_engine.py          # FastAPI app: question → SQL → answer
├── app/
│   ├── index.html               # Web UI
│   ├── style.css
│   └── app.js                   # Calls POST /ask on localhost:8001
├── db/
│   └── schema.sql               # All table definitions + execute_query RPC
├── Meilisearch-csv/             # Drop exported CSVs here before loading
├── token.json                   # OAuth2 token (gitignored — do not commit)
├── oauth-credentials.json       # OAuth2 client secrets (gitignored)
└── .env                         # All credentials (gitignored)
```

### Database Schema (Supabase)

**`ga4_page_metrics`**
| Column | Type | Notes |
|--------|------|-------|
| date | DATE | |
| page_path | TEXT | |
| landing_page | TEXT | |
| source_medium | TEXT | e.g. `google / organic` |
| sessions | INT | |
| total_users | INT | |
| new_users | INT | |
| engaged_sessions | INT | |
| avg_engagement_time_sec | NUMERIC | |
| bounce_rate | NUMERIC | |
| screenpage_views | INT | |
| UNIQUE | | `(date, page_path, source_medium, landing_page)` |

**`gsc_queries`**
| Column | Type | Notes |
|--------|------|-------|
| date | DATE | |
| query | TEXT | Google search query |
| page | TEXT | Landing page URL |
| country | TEXT | 3-letter country code |
| device | TEXT | `DESKTOP`, `MOBILE`, `TABLET` |
| clicks | INT | |
| impressions | INT | |
| ctr | NUMERIC | |
| position | NUMERIC | Average ranking position |
| UNIQUE | | `(date, query, page, country, device)` |

**`gsc_pages`** — same as above without query/country/device

**`ms_top_searches`** — `(date, query_term, search_count)`

**`ms_no_results`** — `(date, query_term, search_count)`

**`ms_countries`** — `(date, country_code, search_count)`

> Note: Meilisearch `date` stores the **start date** of the exported period, not a per-day value. This is a platform limitation — analytics exports are aggregated over a date range.

### Google Authentication

Service accounts were not used. Authentication uses **OAuth2 with a stored refresh token**:

- Run `python auth_setup.py` once — opens a browser, user logs in with the Google account that has Owner access to GSC and access to GA4
- Saves `token.json` with a refresh token
- Both `sync_ga4.py` and `sync_gsc.py` load credentials from `token.json` and auto-refresh when expired
- `oauth-credentials.json` holds the OAuth2 client secrets (Desktop app type, project `890120569248`)

If `token.json` is ever lost or revoked, re-run `python auth_setup.py`.

### AI Query Layer — How It Works

`server/query_engine.py` exposes a single endpoint: `POST /ask`

1. Receives `{ "question": "..." }`
2. Sends the question to **Claude Haiku** with a system prompt containing the full database schema — generates a SQL SELECT statement
3. Strips markdown fences and trailing semicolons from the generated SQL
4. Executes the SQL via Supabase's `execute_query` RPC function (read-only, SELECT only)
5. Sends the question + raw rows back to **Claude Haiku** — generates a plain-English answer
6. Returns `{ "answer": "...", "sql": "...", "row_count": N }`

Prompt caching (`cache_control: ephemeral`) is applied to both system prompts to reduce latency and cost on repeated calls.

### Running Locally

```bash
# Start the API server
uvicorn server.query_engine:app --port 8001

# Open the UI
# Open app/index.html in a browser
```

### Running Sync Manually

```bash
# GA4 — sync last N months
python sync/sync_ga4.py 12

# GSC — sync last N days
python sync/sync_gsc.py 90

# Meilisearch — load CSVs from Meilisearch-csv/ folder
python sync/load_meilisearch_csv.py
```

### Meilisearch CSV Workflow (Monthly)

The Meilisearch analytics API is not accessible on the current plan. The workaround:

1. Log into [cloud.meilisearch.com](https://cloud.meilisearch.com)
2. Go to **Analytics → export** for each of the 3 report types:
   - Searched queries
   - Searches without results
   - Countries
3. Set the date range to the last 30 days
4. Drop all 3 CSVs into `Meilisearch-csv/`
5. Run `python sync/load_meilisearch_csv.py`

The script reads the date range from the filename automatically.

### Supabase Configuration Required

Row Level Security must be **disabled** on all 6 tables (sync scripts write via the anon key):

```sql
ALTER TABLE ga4_page_metrics DISABLE ROW LEVEL SECURITY;
ALTER TABLE gsc_queries DISABLE ROW LEVEL SECURITY;
ALTER TABLE gsc_pages DISABLE ROW LEVEL SECURITY;
ALTER TABLE ms_top_searches DISABLE ROW LEVEL SECURITY;
ALTER TABLE ms_no_results DISABLE ROW LEVEL SECURITY;
ALTER TABLE ms_countries DISABLE ROW LEVEL SECURITY;
```

Performance indexes (run once):

```sql
CREATE INDEX IF NOT EXISTS idx_ga4_date ON ga4_page_metrics(date);
CREATE INDEX IF NOT EXISTS idx_gsc_queries_date ON gsc_queries(date);
CREATE INDEX IF NOT EXISTS idx_gsc_pages_date ON gsc_pages(date);
CREATE INDEX IF NOT EXISTS idx_ms_top_date ON ms_top_searches(date);
```

The `execute_query` RPC function must have `statement_timeout = '30s'` — see `db/schema.sql` for the full definition.

### Environment Variables (`.env`)

| Variable | Purpose |
|----------|---------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase anon key |
| `GA4_PROPERTY_ID` | GA4 numeric property ID |
| `GSC_SITE_URL` | `sc-domain:subjecttoclimate.org` |
| `MEILISEARCH_URL` | Meilisearch Cloud instance URL |
| `MEILISEARCH_API_KEY` | Meilisearch API key |
| `ANTHROPIC_API_KEY` | Claude API key |
| `GOOGLE_TOKEN_FILE` | Path to token.json (defaults to `token.json`) |
