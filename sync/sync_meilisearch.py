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
