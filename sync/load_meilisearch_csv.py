import os
import csv
import sys
import re
from datetime import date
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

CSV_DIR = os.path.join(os.path.dirname(__file__), "..", "Meilisearch-csv")

# Filename patterns: ...-searched_queries.csv, ...-searches_without_results.csv, ...-countries_searches.csv
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})")

QUERY_SUFFIX = "searched_queries.csv"
NO_RESULT_SUFFIX = "searches_without_results.csv"
COUNTRY_SUFFIX = "countries_searches.csv"


def _parse_date_range(filename):
    m = DATE_RE.search(filename)
    if not m:
        raise ValueError(f"Cannot parse date range from filename: {filename}")
    return m.group(1), m.group(2)


def _read_csv(filepath):
    with open(filepath, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_file(filepath, supabase_client):
    name = os.path.basename(filepath)
    start_date, end_date = _parse_date_range(name)
    rows = _read_csv(filepath)

    if name.endswith(QUERY_SUFFIX):
        records = [
            {"date": start_date, "query_term": r["name"], "search_count": int(r["value"])}
            for r in rows if r.get("name") and r.get("value")
        ]
        supabase_client.table("ms_top_searches").upsert(records, on_conflict="date,query_term").execute()
        print(f"[ms] top searches {start_date}/{end_date}: {len(records)} rows")

    elif name.endswith(NO_RESULT_SUFFIX):
        records = [
            {"date": start_date, "query_term": r["name"], "search_count": int(r["value"])}
            for r in rows if r.get("name") and r.get("value")
        ]
        supabase_client.table("ms_no_results").upsert(records, on_conflict="date,query_term").execute()
        print(f"[ms] no-results {start_date}/{end_date}: {len(records)} rows")

    elif name.endswith(COUNTRY_SUFFIX):
        records = [
            {"date": start_date, "country_code": r["name"], "search_count": int(r["value"])}
            for r in rows if r.get("name") and r.get("value")
        ]
        supabase_client.table("ms_countries").upsert(records, on_conflict="date,country_code").execute()
        print(f"[ms] countries {start_date}/{end_date}: {len(records)} rows")

    else:
        print(f"[ms] skipping unrecognised file: {name}")


def run():
    supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    csv_files = [
        os.path.join(CSV_DIR, f)
        for f in os.listdir(CSV_DIR)
        if f.endswith(".csv")
    ]
    if not csv_files:
        print("No CSV files found in Meilisearch-csv/")
        return
    for filepath in sorted(csv_files):
        load_file(filepath, supabase_client)


if __name__ == "__main__":
    run()
