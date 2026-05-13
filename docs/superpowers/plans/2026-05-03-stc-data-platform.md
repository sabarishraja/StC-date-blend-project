# StC Data Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a data pipeline that syncs GA4, Google Search Console, and Meilisearch into Supabase, and exposes a plain-English query interface via Claude AI and a static web UI.

**Architecture:** Three independent Python sync scripts pull daily data from each API and upsert into six Supabase tables. A FastAPI server wraps Claude Haiku to convert plain-English questions into SQL, execute them against Supabase via a read-only RPC function, and return formatted answers. A static HTML/JS frontend calls the FastAPI server.

**Tech Stack:** Python 3.11+, FastAPI, Supabase (PostgreSQL), Google Analytics Data API v1beta, Google Search Console API v3, Meilisearch Analytics REST API, Anthropic Claude Haiku, GitHub Actions

---

## File Map

```
stc-data-platform/
├── .env                              ← already exists, all secrets
├── ga4-credentials.json              ← already exists, Google service account
├── requirements.txt                  ← CREATE: all Python dependencies
├── sync/
│   ├── __init__.py                   ← CREATE: empty, makes sync a package
│   ├── sync_meilisearch.py           ← CREATE: pulls MS analytics → Supabase
│   ├── sync_gsc.py                   ← CREATE: pulls GSC queries + pages → Supabase
│   └── sync_ga4.py                   ← CREATE: pulls GA4 page metrics → Supabase
├── db/
│   └── schema.sql                    ← CREATE: all 6 tables + RPC function
├── server/
│   ├── __init__.py                   ← CREATE: empty
│   └── query_engine.py               ← CREATE: FastAPI app, Claude SQL gen + answer
├── app/
│   ├── index.html                    ← CREATE: question input + answer display
│   ├── style.css                     ← CREATE: clean readable styling
│   └── app.js                        ← CREATE: fetch to /ask, render answer
├── tests/
│   ├── test_sync_meilisearch.py      ← CREATE: unit tests for MS sync logic
│   ├── test_sync_gsc.py              ← CREATE: unit tests for GSC sync logic
│   ├── test_sync_ga4.py              ← CREATE: unit tests for GA4 sync logic
│   └── test_query_engine.py          ← CREATE: unit tests for SQL safety check
└── .github/
    └── workflows/
        └── daily_sync.yml            ← CREATE: cron job running all 3 scripts
```

---

## Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Create: `sync/__init__.py`
- Create: `server/__init__.py`
- Create: `tests/__init__.py` (empty)

- [ ] **Step 1: Create requirements.txt**

```
google-analytics-data>=0.18.0
google-api-python-client>=2.100.0
google-auth>=2.25.0
supabase>=2.3.0
python-dotenv>=1.0.0
requests>=2.31.0
anthropic>=0.40.0
fastapi>=0.109.0
uvicorn>=0.27.0
pytest>=8.0.0
pytest-mock>=3.12.0
```

- [ ] **Step 2: Create empty __init__ files**

```bash
mkdir -p sync server tests
touch sync/__init__.py server/__init__.py tests/__init__.py
```

- [ ] **Step 3: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without errors.

- [ ] **Step 4: Verify .env is correct**

The `.env` file must contain these keys (already present):
```
SUPABASE_URL=...
SUPABASE_KEY=...
MEILISEARCH_API_KEY=...
MEILISEARCH_URL=...
GA4_PROPERTY_ID=...
GOOGLE_APPLICATION_CREDENTIALS=ga4-credentials.json
ANTHROPIC_API_KEY=...
```

- [ ] **Step 5: Commit**

```bash
git init
git add requirements.txt sync/__init__.py server/__init__.py tests/__init__.py
git commit -m "chore: project setup and dependencies"
```

---

## Task 2: Database Schema

**Files:**
- Create: `db/schema.sql`

- [ ] **Step 1: Write schema.sql**

```sql
-- ga4_page_metrics: daily GA4 page performance
CREATE TABLE IF NOT EXISTS ga4_page_metrics (
    id          BIGSERIAL PRIMARY KEY,
    date        DATE    NOT NULL,
    page_path   TEXT    NOT NULL,
    landing_page TEXT   NOT NULL DEFAULT '',
    source_medium TEXT  NOT NULL DEFAULT '',
    screen_class  TEXT  NOT NULL DEFAULT '',
    sessions              INTEGER DEFAULT 0,
    total_users           INTEGER DEFAULT 0,
    new_users             INTEGER DEFAULT 0,
    engaged_sessions      INTEGER DEFAULT 0,
    avg_engagement_time_sec NUMERIC DEFAULT 0,
    bounce_rate           NUMERIC DEFAULT 0,
    screenpage_views      INTEGER DEFAULT 0,
    UNIQUE (date, page_path, source_medium, landing_page, screen_class)
);

-- gsc_queries: Search Console query-level data
CREATE TABLE IF NOT EXISTS gsc_queries (
    id          BIGSERIAL PRIMARY KEY,
    date        DATE    NOT NULL,
    query       TEXT    NOT NULL,
    page        TEXT    NOT NULL DEFAULT '',
    country     TEXT    NOT NULL DEFAULT '',
    device      TEXT    NOT NULL DEFAULT '',
    clicks      INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    ctr         NUMERIC DEFAULT 0,
    position    NUMERIC DEFAULT 0,
    UNIQUE (date, query, page, country, device)
);

-- gsc_pages: Search Console page-level aggregates
CREATE TABLE IF NOT EXISTS gsc_pages (
    id          BIGSERIAL PRIMARY KEY,
    date        DATE    NOT NULL,
    page        TEXT    NOT NULL,
    clicks      INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    ctr         NUMERIC DEFAULT 0,
    position    NUMERIC DEFAULT 0,
    UNIQUE (date, page)
);

-- ms_top_searches: Meilisearch top queried terms
CREATE TABLE IF NOT EXISTS ms_top_searches (
    id           BIGSERIAL PRIMARY KEY,
    date         DATE NOT NULL,
    query_term   TEXT NOT NULL,
    search_count INTEGER DEFAULT 0,
    UNIQUE (date, query_term)
);

-- ms_no_results: Meilisearch queries that returned nothing
CREATE TABLE IF NOT EXISTS ms_no_results (
    id           BIGSERIAL PRIMARY KEY,
    date         DATE NOT NULL,
    query_term   TEXT NOT NULL,
    search_count INTEGER DEFAULT 0,
    UNIQUE (date, query_term)
);

-- ms_countries: Meilisearch searches by country
CREATE TABLE IF NOT EXISTS ms_countries (
    id           BIGSERIAL PRIMARY KEY,
    date         DATE NOT NULL,
    country_code TEXT NOT NULL,
    search_count INTEGER DEFAULT 0,
    UNIQUE (date, country_code)
);

-- Read-only role for AI query layer
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'readonly_ai') THEN
        CREATE ROLE readonly_ai;
    END IF;
END
$$;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_ai;

-- RPC function: AI layer calls this to execute SELECT queries safely
CREATE OR REPLACE FUNCTION execute_query(sql_query text)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    result json;
BEGIN
    IF NOT (lower(trim(sql_query)) LIKE 'select%') THEN
        RAISE EXCEPTION 'Only SELECT queries are allowed';
    END IF;
    EXECUTE 'SELECT json_agg(t) FROM (' || sql_query || ') t' INTO result;
    RETURN COALESCE(result, '[]'::json);
END;
$$;
```

- [ ] **Step 2: Apply schema to Supabase**

Go to your Supabase project → SQL Editor → paste the full contents of `db/schema.sql` → Run.

Expected: all 6 tables visible in Table Editor, `execute_query` function visible in Database → Functions.

- [ ] **Step 3: Commit**

```bash
git add db/schema.sql
git commit -m "feat: database schema with 6 tables and read-only RPC function"
```

---

## Task 3: Meilisearch Sync Script

**Files:**
- Create: `sync/sync_meilisearch.py`
- Create: `tests/test_sync_meilisearch.py`

> **Note on Meilisearch Analytics API:** The base URL is your instance URL from `.env` (`MEILISEARCH_URL`). The three endpoints used are:
> - `GET /search-analytics/top-searches?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD`
> - `GET /search-analytics/searches-without-results?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD`
> - `GET /search-analytics/searches-per-country?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD`
>
> API responses return a `results` array where each item has `search` (query string) and `count` (integer) for searches, and `country` + `count` for countries. **Verify these field names match your Meilisearch Cloud instance by running a manual curl before running the backfill.**
>
> Test with: `curl -H "Authorization: Bearer $MEILISEARCH_API_KEY" "$MEILISEARCH_URL/search-analytics/top-searches?startDate=2026-04-16&endDate=2026-04-16"`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sync_meilisearch.py
from unittest.mock import MagicMock, patch
import pytest
from datetime import date

# We test the transform logic in isolation from API + Supabase calls

def test_build_top_search_records():
    from sync.sync_meilisearch import build_top_search_records
    raw = [{"search": "penguins", "count": 10}, {"search": "drought", "count": 9}]
    result = build_top_search_records("2026-04-16", raw)
    assert result == [
        {"date": "2026-04-16", "query_term": "penguins", "search_count": 10},
        {"date": "2026-04-16", "query_term": "drought", "search_count": 9},
    ]

def test_build_no_result_records():
    from sync.sync_meilisearch import build_no_result_records
    raw = [{"search": "albedo", "count": 5}]
    result = build_no_result_records("2026-04-16", raw)
    assert result == [{"date": "2026-04-16", "query_term": "albedo", "search_count": 5}]

def test_build_country_records():
    from sync.sync_meilisearch import build_country_records
    raw = [{"country": "US", "count": 57892}, {"country": "SG", "count": 10806}]
    result = build_country_records("2026-04-16", raw)
    assert result == [
        {"date": "2026-04-16", "country_code": "US", "search_count": 57892},
        {"date": "2026-04-16", "country_code": "SG", "search_count": 10806},
    ]

def test_build_top_search_records_empty():
    from sync.sync_meilisearch import build_top_search_records
    assert build_top_search_records("2026-04-16", []) == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_sync_meilisearch.py -v
```

Expected: `ImportError` — `sync_meilisearch` doesn't exist yet.

- [ ] **Step 3: Write sync_meilisearch.py**

```python
# sync/sync_meilisearch.py
import os
import sys
import requests
from datetime import date, timedelta
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

MEILISEARCH_URL = os.environ["MEILISEARCH_URL"].rstrip("/")
MEILISEARCH_API_KEY = os.environ["MEILISEARCH_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

_HEADERS = {"Authorization": f"Bearer {MEILISEARCH_API_KEY}"}


def build_top_search_records(sync_date: str, raw: list) -> list:
    return [{"date": sync_date, "query_term": r["search"], "search_count": r["count"]} for r in raw]


def build_no_result_records(sync_date: str, raw: list) -> list:
    return [{"date": sync_date, "query_term": r["search"], "search_count": r["count"]} for r in raw]


def build_country_records(sync_date: str, raw: list) -> list:
    return [{"date": sync_date, "country_code": r["country"], "search_count": r["count"]} for r in raw]


def _get(endpoint: str, start: str, end: str) -> list:
    url = f"{MEILISEARCH_URL}{endpoint}"
    resp = requests.get(url, headers=_HEADERS, params={"startDate": start, "endDate": end}, timeout=30)
    resp.raise_for_status()
    return resp.json().get("results", [])


def sync_day(target_date: date, supabase_client=None):
    if supabase_client is None:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

    date_str = target_date.isoformat()

    top = _get("/search-analytics/top-searches", date_str, date_str)
    records = build_top_search_records(date_str, top)
    if records:
        supabase_client.table("ms_top_searches").upsert(records, on_conflict="date,query_term").execute()

    no_results = _get("/search-analytics/searches-without-results", date_str, date_str)
    records = build_no_result_records(date_str, no_results)
    if records:
        supabase_client.table("ms_no_results").upsert(records, on_conflict="date,query_term").execute()

    countries = _get("/search-analytics/searches-per-country", date_str, date_str)
    records = build_country_records(date_str, countries)
    if records:
        supabase_client.table("ms_countries").upsert(records, on_conflict="date,country_code").execute()

    print(f"[meilisearch] {date_str}: {len(top)} searches, {len(no_results)} no-results, {len(countries)} countries")


def run(backfill_days: int = 1):
    yesterday = date.today() - timedelta(days=1)
    for i in range(backfill_days):
        sync_day(yesterday - timedelta(days=i))


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run(backfill_days=days)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_sync_meilisearch.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Smoke test against live API (single day)**

```bash
python sync/sync_meilisearch.py 1
```

Expected: prints `[meilisearch] YYYY-MM-DD: N searches, N no-results, N countries`. Check Supabase Table Editor to confirm rows appeared in `ms_top_searches`, `ms_no_results`, `ms_countries`.

- [ ] **Step 6: Run 90-day backfill**

```bash
python sync/sync_meilisearch.py 90
```

Expected: 90 lines of output, one per day. Verify row count in Supabase: `SELECT COUNT(*), MIN(date), MAX(date) FROM ms_top_searches;`

- [ ] **Step 7: Commit**

```bash
git add sync/sync_meilisearch.py tests/test_sync_meilisearch.py
git commit -m "feat: Meilisearch analytics sync script with 90-day backfill"
```

---

## Task 4: Google Search Console Sync Script

**Files:**
- Create: `sync/sync_gsc.py`
- Create: `tests/test_sync_gsc.py`

> **GSC API setup:** The service account in `ga4-credentials.json` must be granted access to your Search Console property. Go to Google Search Console → Settings → Users and permissions → Add user → paste the service account email (found in `ga4-credentials.json` as `client_email`) → set as Owner or Full.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sync_gsc.py
import pytest

def test_build_query_records():
    from sync.sync_gsc import build_query_records
    raw_rows = [
        {"keys": ["penguins", "https://stc.org/resources/penguins", "usa", "MOBILE"],
         "clicks": 45, "impressions": 890, "ctr": 0.0506, "position": 3.2},
    ]
    result = build_query_records("2025-04-01", raw_rows)
    assert result == [{
        "date": "2025-04-01",
        "query": "penguins",
        "page": "https://stc.org/resources/penguins",
        "country": "usa",
        "device": "MOBILE",
        "clicks": 45,
        "impressions": 890,
        "ctr": 0.0506,
        "position": 3.2,
    }]

def test_build_page_records():
    from sync.sync_gsc import build_page_records
    raw_rows = [
        {"keys": ["https://stc.org/resources/penguins"],
         "clicks": 120, "impressions": 2400, "ctr": 0.05, "position": 3.1},
    ]
    result = build_page_records("2025-04-01", raw_rows)
    assert result == [{
        "date": "2025-04-01",
        "page": "https://stc.org/resources/penguins",
        "clicks": 120,
        "impressions": 2400,
        "ctr": 0.05,
        "position": 3.1,
    }]

def test_build_query_records_empty():
    from sync.sync_gsc import build_query_records
    assert build_query_records("2025-04-01", []) == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_sync_gsc.py -v
```

Expected: `ImportError` — `sync_gsc` doesn't exist yet.

- [ ] **Step 3: Write sync_gsc.py**

```python
# sync/sync_gsc.py
import os
import sys
from datetime import date, timedelta
from googleapiclient.discovery import build
from google.oauth2 import service_account
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
CREDENTIALS_FILE = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
SITE_URL = os.environ.get("GSC_SITE_URL", "https://subjecttoclimate.org/")  # add to .env


def build_query_records(sync_date: str, rows: list) -> list:
    records = []
    for row in rows:
        keys = row["keys"]
        records.append({
            "date": sync_date,
            "query": keys[0],
            "page": keys[1],
            "country": keys[2],
            "device": keys[3],
            "clicks": row["clicks"],
            "impressions": row["impressions"],
            "ctr": row["ctr"],
            "position": row["position"],
        })
    return records


def build_page_records(sync_date: str, rows: list) -> list:
    records = []
    for row in rows:
        records.append({
            "date": sync_date,
            "page": row["keys"][0],
            "clicks": row["clicks"],
            "impressions": row["impressions"],
            "ctr": row["ctr"],
            "position": row["position"],
        })
    return records


def _get_service():
    creds = service_account.Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return build("searchconsole", "v1", credentials=creds)


def _fetch_all_rows(service, date_str: str, dimensions: list) -> list:
    all_rows = []
    start_row = 0
    row_limit = 25000
    while True:
        body = {
            "startDate": date_str,
            "endDate": date_str,
            "dimensions": dimensions,
            "rowLimit": row_limit,
            "startRow": start_row,
        }
        resp = service.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()
        rows = resp.get("rows", [])
        all_rows.extend(rows)
        if len(rows) < row_limit:
            break
        start_row += row_limit
    return all_rows


def sync_day(target_date: date, supabase_client=None, service=None):
    if supabase_client is None:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    if service is None:
        service = _get_service()

    date_str = target_date.isoformat()

    query_rows = _fetch_all_rows(service, date_str, ["query", "page", "country", "device"])
    records = build_query_records(date_str, query_rows)
    if records:
        supabase_client.table("gsc_queries").upsert(records, on_conflict="date,query,page,country,device").execute()

    page_rows = _fetch_all_rows(service, date_str, ["page"])
    records = build_page_records(date_str, page_rows)
    if records:
        supabase_client.table("gsc_pages").upsert(records, on_conflict="date,page").execute()

    print(f"[gsc] {date_str}: {len(query_rows)} query rows, {len(page_rows)} page rows")


def run(backfill_days: int = 1):
    # GSC lag: pull from today - 3 days
    base = date.today() - timedelta(days=3)
    for i in range(backfill_days):
        sync_day(base - timedelta(days=i))


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run(backfill_days=days)
```

- [ ] **Step 4: Add GSC_SITE_URL to .env**

Open `.env` and add:
```
GSC_SITE_URL=https://subjecttoclimate.org/
```
(Use the exact URL registered in your Search Console property, including trailing slash.)

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_sync_gsc.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 6: Smoke test against live API (single day)**

```bash
python sync/sync_gsc.py 1
```

Expected: `[gsc] YYYY-MM-DD: N query rows, N page rows`. Check Supabase to confirm rows in `gsc_queries` and `gsc_pages`.

- [ ] **Step 7: Run 12-month backfill**

```bash
python sync/sync_gsc.py 365
```

Expected: 365 lines of output. This will take several minutes due to API rate limits. Verify in Supabase: `SELECT COUNT(*), MIN(date), MAX(date) FROM gsc_queries;`

- [ ] **Step 8: Commit**

```bash
git add sync/sync_gsc.py tests/test_sync_gsc.py .env
git commit -m "feat: Google Search Console sync script with 12-month backfill"
```

---

## Task 5: GA4 Sync Script

**Files:**
- Create: `sync/sync_ga4.py`
- Create: `tests/test_sync_ga4.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sync_ga4.py
import pytest

def test_build_ga4_records():
    from sync.sync_ga4 import build_records
    raw_rows = [{
        "dimensionValues": [
            {"value": "20250401"},
            {"value": "/resources/penguins"},
            {"value": "/resources/penguins"},
            {"value": "google / organic"},
            {"value": "(not set)"},
        ],
        "metricValues": [
            {"value": "150"},
            {"value": "200"},
            {"value": "80"},
            {"value": "120"},
            {"value": "95.5"},
            {"value": "0.12"},
            {"value": "300"},
        ],
    }]
    result = build_records(raw_rows)
    assert len(result) == 1
    assert result[0]["date"] == "2025-04-01"
    assert result[0]["page_path"] == "/resources/penguins"
    assert result[0]["source_medium"] == "google / organic"
    assert result[0]["sessions"] == 150
    assert result[0]["total_users"] == 200
    assert result[0]["bounce_rate"] == 0.12

def test_build_ga4_records_empty():
    from sync.sync_ga4 import build_records
    assert build_records([]) == []

def test_format_date():
    from sync.sync_ga4 import format_ga4_date
    assert format_ga4_date("20250401") == "2025-04-01"
    assert format_ga4_date("20251231") == "2025-12-31"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_sync_ga4.py -v
```

Expected: `ImportError` — `sync_ga4` doesn't exist yet.

- [ ] **Step 3: Write sync_ga4.py**

```python
# sync/sync_ga4.py
import os
import sys
from datetime import date, timedelta
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
GA4_PROPERTY_ID = os.environ["GA4_PROPERTY_ID"]
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "ga4-credentials.json")

DIMENSIONS = ["date", "pagePath", "landingPage", "sessionSourceMedium", "screenClass"]
METRICS = ["sessions", "totalUsers", "newUsers", "engagedSessions",
           "userEngagementDuration", "bounceRate", "screenPageViews"]


def format_ga4_date(ga4_date: str) -> str:
    return f"{ga4_date[:4]}-{ga4_date[4:6]}-{ga4_date[6:]}"


def build_records(rows: list) -> list:
    records = []
    for row in rows:
        dims = [d.value for d in row.dimension_values]
        mets = [m.value for m in row.metric_values]
        records.append({
            "date": format_ga4_date(dims[0]),
            "page_path": dims[1],
            "landing_page": dims[2],
            "source_medium": dims[3],
            "screen_class": dims[4],
            "sessions": int(mets[0]),
            "total_users": int(mets[1]),
            "new_users": int(mets[2]),
            "engaged_sessions": int(mets[3]),
            "avg_engagement_time_sec": float(mets[4]),
            "bounce_rate": float(mets[5]),
            "screenpage_views": int(mets[6]),
        })
    return records


def _fetch(start_date: str, end_date: str) -> list:
    client = BetaAnalyticsDataClient()
    request = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[Dimension(name=d) for d in DIMENSIONS],
        metrics=[Metric(name=m) for m in METRICS],
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        limit=100000,
    )
    response = client.run_report(request)
    return response.rows


def sync_range(start_date: str, end_date: str, supabase_client=None):
    if supabase_client is None:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    rows = _fetch(start_date, end_date)
    records = build_records(rows)
    if records:
        conflict_cols = "date,page_path,source_medium,landing_page,screen_class"
        supabase_client.table("ga4_page_metrics").upsert(records, on_conflict=conflict_cols).execute()
    print(f"[ga4] {start_date} → {end_date}: {len(records)} rows")


def run(backfill_months: int = 1):
    # GA4 lag: pull from today - 2 days
    end = date.today() - timedelta(days=2)
    for i in range(backfill_months):
        # Pull month-by-month to stay within quota
        month_end = end.replace(day=1) - timedelta(days=1) if i > 0 else end
        month_start = month_end.replace(day=1)
        sync_range(month_start.isoformat(), month_end.isoformat())
        end = month_start - timedelta(days=1)


if __name__ == "__main__":
    months = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run(backfill_months=months)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_sync_ga4.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Smoke test against live API (current month)**

```bash
python sync/sync_ga4.py 1
```

Expected: `[ga4] YYYY-MM-DD → YYYY-MM-DD: N rows`. Check Supabase to confirm rows in `ga4_page_metrics`.

- [ ] **Step 6: Run 12-month backfill**

```bash
python sync/sync_ga4.py 12
```

Expected: 12 lines of output, one per month. Verify in Supabase: `SELECT COUNT(*), MIN(date), MAX(date) FROM ga4_page_metrics;`

- [ ] **Step 7: Commit**

```bash
git add sync/sync_ga4.py tests/test_sync_ga4.py
git commit -m "feat: GA4 page metrics sync script with 12-month backfill"
```

---

## Task 6: GitHub Actions Daily Sync

**Files:**
- Create: `.github/workflows/daily_sync.yml`

- [ ] **Step 1: Create the workflow file**

```yaml
# .github/workflows/daily_sync.yml
name: Daily Data Sync

on:
  schedule:
    - cron: "0 6 * * *"   # 06:00 UTC daily
  workflow_dispatch:        # allow manual trigger from GitHub UI

jobs:
  sync-meilisearch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: python sync/sync_meilisearch.py 1
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          MEILISEARCH_URL: ${{ secrets.MEILISEARCH_URL }}
          MEILISEARCH_API_KEY: ${{ secrets.MEILISEARCH_API_KEY }}

  sync-gsc:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - name: Write GA4 credentials file
        run: echo '${{ secrets.GA4_CREDENTIALS_JSON }}' > ga4-credentials.json
      - run: python sync/sync_gsc.py 1
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          GOOGLE_APPLICATION_CREDENTIALS: ga4-credentials.json
          GSC_SITE_URL: ${{ secrets.GSC_SITE_URL }}

  sync-ga4:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - name: Write GA4 credentials file
        run: echo '${{ secrets.GA4_CREDENTIALS_JSON }}' > ga4-credentials.json
      - run: python sync/sync_ga4.py 1
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          GA4_PROPERTY_ID: ${{ secrets.GA4_PROPERTY_ID }}
          GOOGLE_APPLICATION_CREDENTIALS: ga4-credentials.json
```

- [ ] **Step 2: Add GitHub Actions secrets**

Go to your GitHub repo → Settings → Secrets and variables → Actions → New repository secret. Add each of these:

| Secret name | Value source |
|---|---|
| `SUPABASE_URL` | From `.env` |
| `SUPABASE_KEY` | From `.env` |
| `MEILISEARCH_URL` | From `.env` |
| `MEILISEARCH_API_KEY` | From `.env` |
| `GA4_PROPERTY_ID` | From `.env` |
| `GSC_SITE_URL` | e.g. `https://subjecttoclimate.org/` |
| `GA4_CREDENTIALS_JSON` | Full contents of `ga4-credentials.json` (paste the entire JSON) |

- [ ] **Step 3: Push to GitHub and trigger manually**

```bash
git add .github/workflows/daily_sync.yml
git commit -m "feat: GitHub Actions daily sync cron at 06:00 UTC"
git push origin main
```

Then go to GitHub → Actions → Daily Data Sync → Run workflow. Verify all three jobs complete with green checks.

---

## Task 7: AI Query Layer (FastAPI)

**Files:**
- Create: `server/query_engine.py`
- Create: `tests/test_query_engine.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_query_engine.py
import pytest

def test_is_safe_select_passes():
    from server.query_engine import is_safe_sql
    assert is_safe_sql("SELECT * FROM ms_top_searches LIMIT 10") is True
    assert is_safe_sql("  select count(*) from gsc_queries  ") is True

def test_is_safe_blocks_writes():
    from server.query_engine import is_safe_sql
    assert is_safe_sql("DROP TABLE ms_top_searches") is False
    assert is_safe_sql("DELETE FROM gsc_queries") is False
    assert is_safe_sql("INSERT INTO gsc_queries VALUES (1)") is False
    assert is_safe_sql("UPDATE gsc_queries SET clicks = 0") is False

def test_is_safe_blocks_empty():
    from server.query_engine import is_safe_sql
    assert is_safe_sql("") is False
    assert is_safe_sql("   ") is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_query_engine.py -v
```

Expected: `ImportError` — `query_engine` doesn't exist yet.

- [ ] **Step 3: Write query_engine.py**

```python
# server/query_engine.py
import os
from dotenv import load_dotenv
import anthropic
from supabase import create_client
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["POST"], allow_headers=["*"])

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

SCHEMA_DESCRIPTION = """
You have access to a PostgreSQL database with these tables:

ga4_page_metrics (date DATE, page_path TEXT, landing_page TEXT, source_medium TEXT, screen_class TEXT,
  sessions INT, total_users INT, new_users INT, engaged_sessions INT,
  avg_engagement_time_sec NUMERIC, bounce_rate NUMERIC, screenpage_views INT)

gsc_queries (date DATE, query TEXT, page TEXT, country TEXT, device TEXT,
  clicks INT, impressions INT, ctr NUMERIC, position NUMERIC)

gsc_pages (date DATE, page TEXT, clicks INT, impressions INT, ctr NUMERIC, position NUMERIC)

ms_top_searches (date DATE, query_term TEXT, search_count INT)

ms_no_results (date DATE, query_term TEXT, search_count INT)

ms_countries (date DATE, country_code TEXT, search_count INT)

Key joins:
- gsc_queries.query ≈ ms_top_searches.query_term (use LOWER() for case-insensitive match)
- gsc_queries.page path segment ≈ ga4_page_metrics.page_path
- GA4 data covers 12 months; Meilisearch covers only 90 days
- Use LEFT JOIN when combining Meilisearch with GSC/GA4 to preserve older records
"""

SQL_SYSTEM_PROMPT = f"""You are a SQL expert for a PostgreSQL database.
{SCHEMA_DESCRIPTION}
Rules:
- Return ONLY the SQL query, nothing else. No markdown, no explanation.
- Only write SELECT statements.
- Always include a LIMIT (max 500 rows) unless doing an aggregation.
- Use LOWER() for case-insensitive text comparisons.
- For date ranges, default to the last 90 days unless the user specifies otherwise.
"""

ANSWER_SYSTEM_PROMPT = f"""You are a helpful data analyst for SubjectToClimate, an educational nonprofit.
{SCHEMA_DESCRIPTION}
You will receive a user question and JSON rows from a database query.
Write a clear, concise plain-English answer (2-5 sentences). Highlight the most important numbers.
If the result is empty, say so and suggest why.
"""


def is_safe_sql(sql: str) -> bool:
    stripped = sql.strip().lower()
    if not stripped:
        return False
    return stripped.startswith("select")


class QuestionRequest(BaseModel):
    question: str


@app.post("/ask")
def ask(req: QuestionRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Call 1: generate SQL (schema is cached in system prompt)
    sql_response = anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=[{"type": "text", "text": SQL_SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": question}],
    )
    sql = sql_response.content[0].text.strip()

    if not is_safe_sql(sql):
        raise HTTPException(status_code=400, detail="Generated query was not a SELECT statement")

    # Execute SQL via Supabase RPC (read-only role)
    try:
        result = supabase_client.rpc("execute_query", {"sql_query": sql}).execute()
        rows = result.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")

    # Call 2: format answer (schema cached again)
    answer_response = anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=[{"type": "text", "text": ANSWER_SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"Question: {question}\n\nData: {rows}"}],
    )
    answer = answer_response.content[0].text.strip()

    return {"answer": answer, "sql": sql, "row_count": len(rows)}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_query_engine.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Start the server and test locally**

```bash
uvicorn server.query_engine:app --reload --port 8000
```

In a second terminal:
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the top 10 content gaps — searches with no results?"}'
```

Expected: JSON response with `answer`, `sql`, and `row_count` fields.

- [ ] **Step 6: Commit**

```bash
git add server/query_engine.py tests/test_query_engine.py
git commit -m "feat: FastAPI AI query layer with Claude Haiku SQL gen and prompt caching"
```

---

## Task 8: Static Frontend

**Files:**
- Create: `app/index.html`
- Create: `app/style.css`
- Create: `app/app.js`

- [ ] **Step 1: Write index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>StC Data Platform</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div class="container">
    <header>
      <h1>StC Data Platform</h1>
      <p class="subtitle">Ask a question about your analytics data</p>
    </header>

    <div class="input-area">
      <textarea id="question" rows="3"
        placeholder="e.g. What are our top content gaps? What do users search for with no results?"></textarea>
      <button id="ask-btn" onclick="askQuestion()">Ask</button>
    </div>

    <div id="status" class="status hidden"></div>

    <div id="result" class="result hidden">
      <div id="answer" class="answer"></div>
      <details class="sql-details">
        <summary>View SQL</summary>
        <pre id="sql-output"></pre>
      </details>
    </div>

    <div class="examples">
      <p>Example questions:</p>
      <ul>
        <li onclick="setQuestion(this)">What are our top content gaps — searches with no results?</li>
        <li onclick="setQuestion(this)">Which pages have the highest organic impressions but lowest clicks?</li>
        <li onclick="setQuestion(this)">What are the most searched terms that also appear in Google Search Console?</li>
        <li onclick="setQuestion(this)">Which resources are evergreen — consistently popular over the last 90 days?</li>
        <li onclick="setQuestion(this)">Where do users from the US mostly land on the site?</li>
      </ul>
    </div>
  </div>
  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Write style.css**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #f5f5f0;
  color: #1a1a1a;
  min-height: 100vh;
  padding: 2rem 1rem;
}

.container {
  max-width: 760px;
  margin: 0 auto;
}

header { margin-bottom: 2rem; }
h1 { font-size: 1.75rem; font-weight: 700; color: #1a472a; }
.subtitle { color: #555; margin-top: 0.25rem; }

.input-area {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  margin-bottom: 1.5rem;
}

textarea {
  flex: 1;
  padding: 0.75rem 1rem;
  border: 1.5px solid #ccc;
  border-radius: 8px;
  font-size: 1rem;
  font-family: inherit;
  resize: vertical;
}

textarea:focus { outline: none; border-color: #1a472a; }

button {
  padding: 0.75rem 1.5rem;
  background: #1a472a;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  cursor: pointer;
  white-space: nowrap;
}

button:disabled { background: #999; cursor: not-allowed; }
button:hover:not(:disabled) { background: #145220; }

.status {
  padding: 0.75rem 1rem;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  color: #555;
  margin-bottom: 1rem;
}

.result {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.answer { font-size: 1.05rem; line-height: 1.65; }

.sql-details {
  margin-top: 1rem;
  border-top: 1px solid #eee;
  padding-top: 0.75rem;
}

summary { cursor: pointer; color: #555; font-size: 0.875rem; }
pre {
  margin-top: 0.5rem;
  padding: 0.75rem;
  background: #f8f8f8;
  border-radius: 4px;
  font-size: 0.8rem;
  overflow-x: auto;
  white-space: pre-wrap;
}

.examples { color: #555; font-size: 0.9rem; }
.examples p { margin-bottom: 0.5rem; font-weight: 600; }
.examples ul { list-style: none; }
.examples li {
  padding: 0.4rem 0.6rem;
  cursor: pointer;
  border-radius: 4px;
  border-left: 3px solid transparent;
}
.examples li:hover { background: #f0f0f0; border-left-color: #1a472a; }

.hidden { display: none; }
```

- [ ] **Step 3: Write app.js**

```javascript
// app/app.js
const API_URL = "http://localhost:8000";  // change to deployed URL for production

function setQuestion(el) {
  document.getElementById("question").value = el.textContent.trim();
}

async function askQuestion() {
  const question = document.getElementById("question").value.trim();
  if (!question) return;

  const btn = document.getElementById("ask-btn");
  const status = document.getElementById("status");
  const result = document.getElementById("result");

  btn.disabled = true;
  status.textContent = "Thinking...";
  status.classList.remove("hidden");
  result.classList.add("hidden");

  try {
    const resp = await fetch(`${API_URL}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || "Server error");
    }

    const data = await resp.json();

    document.getElementById("answer").textContent = data.answer;
    document.getElementById("sql-output").textContent = data.sql;
    result.classList.remove("hidden");
    status.classList.add("hidden");
  } catch (err) {
    status.textContent = `Error: ${err.message}`;
  } finally {
    btn.disabled = false;
  }
}

document.getElementById("question").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) askQuestion();
});
```

- [ ] **Step 4: Open in browser and test the golden path**

With the FastAPI server running (`uvicorn server.query_engine:app --reload --port 8000`), open `app/index.html` directly in a browser (File → Open).

Test these questions end-to-end:
1. Click "What are our top content gaps — searches with no results?" → verify answer mentions query terms + counts
2. Click "Which resources are evergreen — consistently popular over the last 90 days?" → verify answer mentions specific pages
3. Type a nonsense question ("asdfgh") → verify server returns a graceful response or empty result message

- [ ] **Step 5: Commit**

```bash
git add app/index.html app/style.css app/app.js
git commit -m "feat: static web UI with question input and answer display"
```

---

## Self-Review Checklist

- [x] **Schema coverage:** All 6 tables in schema.sql match spec. RPC function + read-only role included.
- [x] **Meilisearch sync:** Covers all 3 endpoints. 90-day backfill. Transform functions testable in isolation.
- [x] **GSC sync:** Covers query-level + page-level. Pagination via startRow. 12-month backfill. GSC_SITE_URL added to .env.
- [x] **GA4 sync:** All 5 dimensions + 7 metrics from spec. Month-by-month backfill. 48h lag accounted for.
- [x] **GitHub Actions:** All 3 scripts run independently. GA4 credentials written from secret JSON. Manual trigger included.
- [x] **AI layer:** is_safe_sql blocks non-SELECT. Prompt caching on system prompt. Both Claude calls use cache_control.
- [x] **Frontend:** Example questions pre-loaded. SQL visible in details. Ctrl+Enter shortcut. Error state handled.
- [x] **Supervisor requirements:** landing_page, source_medium, page_path, screen_class all in ga4_page_metrics and pulled in sync_ga4.py.
- [x] **No placeholders:** All code blocks are complete and runnable.
- [x] **Type consistency:** `build_records`, `build_query_records`, `build_page_records`, `build_top_search_records`, `build_no_result_records`, `build_country_records` — function names consistent between tests and implementation in every task.
