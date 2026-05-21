# CSV Upload UI — Design Spec

**Date:** 2026-05-20
**Status:** Approved, ready for implementation
**Author:** Sabarinath R. (with Claude)

## Problem

FullStory and Meilisearch data currently reach Supabase through a manual,
developer-only pathway:

1. A teammate exports a CSV from the source web app.
2. A developer drops the file into `Fullstory-csv/` or `Meilisearch-csv/`.
3. A developer runs `python sync/load_fullstory_csv.py` or
   `python sync/load_meilisearch_csv.py` from a local environment with
   Supabase credentials configured.

Step 2 and 3 require a developer with Python, the repo, and credentials —
which makes ingestion a bottleneck. The team has non-technical members who
already have the CSVs but no way to load them.

The FullStory free plan does not expose the Segment Export API, so a
fully API-driven nightly sync (like GA4 and GSC) is not available.
Meilisearch's hosted analytics dashboard does not expose an export API
either. CSV will remain the source-of-truth interface for both.

## Goal

A drag-and-drop upload page in the existing web UI that lets a
non-technical teammate ingest FullStory and Meilisearch CSVs into Supabase
in seconds, with clear success/error feedback and no developer in the loop.

## Non-goals

- Replacing the existing GitHub Actions daily sync for GA4 / GSC.
- Building a full user authentication system.
- Web-scraping or RPA against FullStory / Meilisearch dashboards.
- Editing or deleting previously uploaded data through the UI.

## Architecture

### New / changed files

- `sync/loaders.py` (new) — shared pure functions:
  - `load_fullstory_dataframe(rows: list[dict], filename: str, supabase) -> LoadResult`
  - `load_meilisearch_dataframe(rows: list[dict], filename: str, supabase) -> LoadResult`
  - `LoadResult` carries `rows_read`, `rows_written`, `date_range`,
    `table`, `errors`.
- `sync/load_fullstory_csv.py`, `sync/load_meilisearch_csv.py` — refactor
  to thin CLI wrappers that read files from disk and call the shared
  loaders. No behavior change for the CLI / GitHub Action path.
- `server/uploads.py` (new) — FastAPI router with:
  - `POST /upload/fullstory` — accepts one CSV file.
  - `POST /upload/meilisearch` — accepts one or more CSV files; routes
    each by filename suffix (`searched_queries.csv`,
    `searches_without_results.csv`, `countries_searches.csv`).
  - Both endpoints validate the `X-Upload-Password` header against
    `UPLOAD_PASSWORD` env var; return 401 on mismatch.
- `server/query_engine.py` — `include_router(uploads.router)`. No other
  changes.
- `app/upload.html`, `app/upload.js`, additions to `app/style.css` — the
  upload page UI.
- `app/index.html` — add a small "Upload data" link in the topbar that
  navigates to `upload.html`.

### Data flow

```
Browser (upload.html)
  └── user picks source + drops CSV
  └── POST multipart/form-data with X-Upload-Password header
       │
       ▼
FastAPI (server/uploads.py)
  └── verify password
  └── parse CSV in memory (csv.DictReader)
  └── call sync.loaders.load_*_dataframe(rows, filename, supabase)
       │
       ▼
sync/loaders.py
  └── existing column-detection + aggregation logic (unchanged behavior)
  └── supabase.table(...).upsert(records, on_conflict=...)
       │
       ▼
Supabase
```

The same `load_*_dataframe` functions back both the CLI scripts (reading
from disk) and the upload endpoints (reading from the HTTP request body).

## Decisions

| Topic | Decision |
| --- | --- |
| Auth | Single shared password via `UPLOAD_PASSWORD` env var. Sent in `X-Upload-Password` header. Cached in `sessionStorage` so the user enters it once per browser session. |
| Duplicate uploads | Upsert by natural key (matches existing loader behavior). Re-uploading the same date range overwrites; no duplicates. |
| File-size cap | 50 MB per file. Configurable via `UPLOAD_MAX_MB` env var. |
| Validation | Loader returns `errors[]` listing any missing required columns or unrecognized filenames. UI displays them prominently. |
| Schema drift | Fail loud — return an explicit error rather than silently dropping data. |
| Multi-file uploads | FullStory: 1 file per request. Meilisearch: up to 3 files per request (one of each suffix). UI lets the user drop all three at once. |
| Date range | Parsed from filename (existing convention: `YYYY-MM-DD_YYYY-MM-DD-*.csv`). FullStory falls back to "today" if absent, matching current behavior. |
| Logging | Server logs source, filename, row counts, and date range for every upload. |

## Error handling

- Missing / wrong password → HTTP 401 with `{detail: "Invalid upload password"}`.
- File over size cap → HTTP 413 with the configured limit.
- CSV unparseable → HTTP 400 with the parser error.
- Missing required columns → HTTP 422 with `{missing_columns: [...]}`.
- Supabase write fails → HTTP 502 with the upstream error message; partial
  success per file is reported (one file may succeed while another fails).

## UI sketch

```
+--------------------------------------------------+
| StC Data — Upload                       [back ←] |
+--------------------------------------------------+
| FullStory                                        |
|  ┌────────────────────────────────────┐          |
|  │  Drop a FullStory CSV here         │          |
|  │  or click to browse                │          |
|  └────────────────────────────────────┘          |
|                                                  |
| Meilisearch  (drop up to 3 CSVs)                 |
|  ┌────────────────────────────────────┐          |
|  │  Drop Meilisearch CSVs here        │          |
|  └────────────────────────────────────┘          |
|                                                  |
| Results                                          |
|  ✓ 2026-05-01 — fs_page_metrics — 412 rows       |
|  ✗ countries_searches.csv — missing "value" col  |
+--------------------------------------------------+
```

## Testing

- Smoke test: run server locally, upload a known-good FullStory CSV from
  `Fullstory-csv/`, confirm row count returned matches direct
  `SELECT count(*)` on Supabase.
- Smoke test: upload all 3 Meilisearch CSVs in one request; confirm three
  separate success entries returned and all three tables populated.
- Negative: upload with wrong password → 401.
- Negative: upload an unrelated CSV → 422 with missing-columns list.
- Re-upload identical file → row counts unchanged in Supabase (upsert
  semantics confirmed).

## Out of scope (future work)

- Adding GA4 / GSC manual upload support (already automated).
- Audit log of who uploaded what (would require per-user accounts).
- Scheduled "is the data fresh?" warning surfaced in the main dashboard.
- Nightly pre-aggregated rollup tables for query performance (separate spec).
