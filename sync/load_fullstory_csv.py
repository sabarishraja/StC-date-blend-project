"""CLI wrapper: read FullStory CSVs from disk and load them via the shared loader."""

import csv
import os
import sys

from dotenv import load_dotenv
from supabase import create_client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sync.loaders import load_fullstory_dataframe  # noqa: E402

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

CSV_DIR = os.path.join(os.path.dirname(__file__), "..", "Fullstory-csv")


def load_file(filepath, supabase_client):
    name = os.path.basename(filepath)
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    result = load_fullstory_dataframe(rows, name, supabase_client)
    if result.errors:
        for err in result.errors:
            print(f"[fullstory] {name}: {err}")
        return
    print(f"[fullstory] Loaded {result.rows_written} page metrics from {name}")


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
