"""CLI wrapper: read Meilisearch CSVs from disk and load them via the shared loader."""

import csv
import os
import sys

from dotenv import load_dotenv
from supabase import create_client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sync.loaders import load_meilisearch_dataframe  # noqa: E402

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

CSV_DIR = os.path.join(os.path.dirname(__file__), "..", "Meilisearch-csv")


def load_file(filepath, supabase_client):
    name = os.path.basename(filepath)
    with open(filepath, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    result = load_meilisearch_dataframe(rows, name, supabase_client)
    if result.errors:
        for err in result.errors:
            print(f"[ms] {name}: {err}")
        return
    if result.date_range:
        print(
            f"[ms] {result.table} {result.date_range[0]}/{result.date_range[1]}: "
            f"{result.rows_written} rows"
        )


def run():
    supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    csv_files = [
        os.path.join(CSV_DIR, f) for f in os.listdir(CSV_DIR) if f.endswith(".csv")
    ]
    if not csv_files:
        print("No CSV files found in Meilisearch-csv/")
        return
    for filepath in sorted(csv_files):
        load_file(filepath, supabase_client)


if __name__ == "__main__":
    run()
