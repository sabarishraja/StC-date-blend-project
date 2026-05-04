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
        month_end = end.replace(day=1) - timedelta(days=1) if i > 0 else end
        month_start = month_end.replace(day=1)
        sync_range(month_start.isoformat(), month_end.isoformat())
        end = month_start - timedelta(days=1)


if __name__ == "__main__":
    months = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run(backfill_months=months)
