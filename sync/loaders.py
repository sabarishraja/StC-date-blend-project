"""Shared CSV loading logic used by both the CLI scripts and the upload API.

Each `load_*_dataframe` function accepts already-parsed rows (a list of
dicts from `csv.DictReader`) plus the source filename (used to extract a
date range) and an authenticated Supabase client. It returns a LoadResult
describing what happened. The functions never raise on bad data — they
collect errors into the result so the caller (CLI or HTTP endpoint) can
present them uniformly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any


DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})")

MS_QUERY_SUFFIX = "searched_queries.csv"
MS_NO_RESULT_SUFFIX = "searches_without_results.csv"
MS_COUNTRY_SUFFIX = "countries_searches.csv"


@dataclass
class LoadResult:
    source: str
    filename: str
    table: str | None = None
    rows_read: int = 0
    rows_written: int = 0
    date_range: tuple[str, str] | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _parse_date_range(filename: str, *, fallback_today: bool = False) -> tuple[str, str] | None:
    m = DATE_RE.search(filename)
    if m:
        return m.group(1), m.group(2)
    if fallback_today:
        today = date.today().isoformat()
        return today, today
    return None


def _parse_num(val: Any, *, as_int: bool = False) -> float | int:
    if val is None or val == "":
        return 0 if as_int else 0.0
    clean = re.sub(r"[^\d.]", "", str(val))
    if not clean:
        return 0 if as_int else 0.0
    return int(float(clean)) if as_int else float(clean)


def load_fullstory_dataframe(
    rows: list[dict],
    filename: str,
    supabase_client,
) -> LoadResult:
    result = LoadResult(source="fullstory", filename=filename)
    date_range = _parse_date_range(filename, fallback_today=True)
    result.date_range = date_range
    start_date = date_range[0]

    result.rows_read = len(rows)
    if not rows:
        result.errors.append("CSV is empty.")
        return result

    headers = list(rows[0].keys())
    col_url = next((h for h in headers if "url" in h.lower() or "page" in h.lower()), None)
    col_rage = next((h for h in headers if "rage" in h.lower()), None)
    col_dead = next((h for h in headers if "dead" in h.lower()), None)
    col_scroll = next((h for h in headers if "scroll" in h.lower()), None)
    col_time = next((h for h in headers if "active" in h.lower() or "time" in h.lower()), None)
    col_sessions = next((h for h in headers if "session" in h.lower() or "count" in h.lower()), None)

    if not col_url:
        result.errors.append("Could not find a Page URL column in the CSV headers.")
        return result

    aggregated: dict[str, dict] = {}
    for r in rows:
        page_url = (r.get(col_url) or "").strip()
        if not page_url:
            continue

        ts = _parse_num(r.get(col_sessions), as_int=True) if col_sessions else 0
        sc = _parse_num(r.get(col_scroll)) if col_scroll else 0.0
        at = _parse_num(r.get(col_time)) if col_time else 0.0
        rc = _parse_num(r.get(col_rage), as_int=True) if col_rage else 0
        dc = _parse_num(r.get(col_dead), as_int=True) if col_dead else 0

        if page_url in aggregated:
            existing = aggregated[page_url]
            existing["total_sessions"] += ts
            existing["rage_clicks"] += rc
            existing["dead_clicks"] += dc
            existing["avg_scroll_depth"] = max(existing["avg_scroll_depth"], sc)
            existing["avg_active_time_sec"] = max(existing["avg_active_time_sec"], at)
        else:
            aggregated[page_url] = {
                "date": start_date,
                "page_url": page_url,
                "total_sessions": ts,
                "avg_scroll_depth": sc,
                "avg_active_time_sec": at,
                "rage_clicks": rc,
                "dead_clicks": dc,
            }

    records = list(aggregated.values())
    result.table = "fs_page_metrics"
    if records:
        supabase_client.table("fs_page_metrics").upsert(
            records, on_conflict="date,page_url"
        ).execute()
        result.rows_written = len(records)
    return result


def load_meilisearch_dataframe(
    rows: list[dict],
    filename: str,
    supabase_client,
) -> LoadResult:
    result = LoadResult(source="meilisearch", filename=filename)
    date_range = _parse_date_range(filename, fallback_today=False)
    if date_range is None:
        result.errors.append(
            f"Cannot parse date range from filename: {filename}. "
            "Expected pattern: YYYY-MM-DD_YYYY-MM-DD-*.csv"
        )
        return result
    result.date_range = date_range
    start_date = date_range[0]

    result.rows_read = len(rows)

    lower = filename.lower()
    if lower.endswith(MS_QUERY_SUFFIX):
        table = "ms_top_searches"
        on_conflict = "date,query_term"
        records = [
            {"date": start_date, "query_term": r["name"], "search_count": int(r["value"])}
            for r in rows if r.get("name") and r.get("value")
        ]
    elif lower.endswith(MS_NO_RESULT_SUFFIX):
        table = "ms_no_results"
        on_conflict = "date,query_term"
        records = [
            {"date": start_date, "query_term": r["name"], "search_count": int(r["value"])}
            for r in rows if r.get("name") and r.get("value")
        ]
    elif lower.endswith(MS_COUNTRY_SUFFIX):
        table = "ms_countries"
        on_conflict = "date,country_code"
        records = [
            {"date": start_date, "country_code": r["name"], "search_count": int(r["value"])}
            for r in rows if r.get("name") and r.get("value")
        ]
    else:
        result.errors.append(
            f"Unrecognised Meilisearch filename: {filename}. "
            f"Expected suffix: {MS_QUERY_SUFFIX}, {MS_NO_RESULT_SUFFIX}, or {MS_COUNTRY_SUFFIX}."
        )
        return result

    result.table = table
    if records:
        supabase_client.table(table).upsert(records, on_conflict=on_conflict).execute()
        result.rows_written = len(records)
    return result
