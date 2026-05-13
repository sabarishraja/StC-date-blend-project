import os
import csv
import re
from datetime import date
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

CSV_DIR = os.path.join(os.path.dirname(__file__), "..", "Fullstory-csv")

# Matches filename like 2026-05-01_2026-05-31-fullstory.csv
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})")

def _parse_date_range(filename):
    m = DATE_RE.search(filename)
    if not m:
        # Fallback to today's date if no date range in filename
        today = date.today().isoformat()
        return today, today
    return m.group(1), m.group(2)

def load_file(filepath, supabase_client):
    name = os.path.basename(filepath)
    start_date, end_date = _parse_date_range(name)
    
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        records = []
        
        # We will map whatever columns FullStory provides.
        # Below is a flexible mapping that looks for keywords in the CSV headers.
        
        headers = reader.fieldnames
        if not headers:
            print(f"Empty CSV: {name}")
            return
            
        # Find which column matches which metric
        col_url = next((h for h in headers if "url" in h.lower() or "page" in h.lower()), None)
        col_rage = next((h for h in headers if "rage" in h.lower()), None)
        col_dead = next((h for h in headers if "dead" in h.lower()), None)
        col_scroll = next((h for h in headers if "scroll" in h.lower()), None)
        col_time = next((h for h in headers if "active" in h.lower() or "time" in h.lower()), None)
        col_sessions = next((h for h in headers if "session" in h.lower() or "count" in h.lower()), None)

        if not col_url:
            print(f"Skipping {name} - could not find a Page URL column.")
            return

        records_dict = {}

        for r in reader:
            page_url = r.get(col_url, "").strip()
            if not page_url:
                continue
                
            # Safely parse numeric values
            def parse_num(val, is_int=False):
                if not val: return 0
                clean = re.sub(r'[^\d.]', '', str(val))
                if not clean: return 0
                return int(float(clean)) if is_int else float(clean)

            ts = parse_num(r.get(col_sessions), True) if col_sessions else 0
            sc = parse_num(r.get(col_scroll), False) if col_scroll else 0.0
            at = parse_num(r.get(col_time), False) if col_time else 0.0
            rc = parse_num(r.get(col_rage), True) if col_rage else 0
            dc = parse_num(r.get(col_dead), True) if col_dead else 0

            if page_url in records_dict:
                existing = records_dict[page_url]
                existing["total_sessions"] += ts
                existing["rage_clicks"] += rc
                existing["dead_clicks"] += dc
                existing["avg_scroll_depth"] = max(existing["avg_scroll_depth"], sc)
                existing["avg_active_time_sec"] = max(existing["avg_active_time_sec"], at)
            else:
                records_dict[page_url] = {
                    "date": start_date, # using start date of the export as the date identifier
                    "page_url": page_url,
                    "total_sessions": ts,
                    "avg_scroll_depth": sc,
                    "avg_active_time_sec": at,
                    "rage_clicks": rc,
                    "dead_clicks": dc
                }

        records = list(records_dict.values())

        if records:
            supabase_client.table("fs_page_metrics").upsert(records, on_conflict="date,page_url").execute()
            print(f"[fullstory] Loaded {len(records)} page metrics from {name}")

def run():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Missing Supabase credentials in .env")
        return
        
    supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    if not os.path.exists(CSV_DIR):
        os.makedirs(CSV_DIR)
        
    csv_files = [os.path.join(CSV_DIR, f) for f in os.listdir(CSV_DIR) if f.endswith(".csv")]
    
    if not csv_files:
        print("No CSV files found in Fullstory-csv/")
        return
        
    for filepath in sorted(csv_files):
        load_file(filepath, supabase_client)

if __name__ == "__main__":
    run()
