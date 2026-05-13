import os
import sys
from datetime import date, timedelta
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
TOKEN_FILE = os.environ.get("GOOGLE_TOKEN_FILE", "token.json")
SITE_URL = os.environ.get("GSC_SITE_URL", "sc-domain:subjecttoclimate.org")


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
    creds = Credentials.from_authorized_user_file(TOKEN_FILE)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
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
        for i in range(0, len(records), 200):
            supabase_client.table("gsc_queries").upsert(
                records[i:i + 200], on_conflict="date,query,page,country,device"
            ).execute()

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
