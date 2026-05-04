# tests/test_sync_meilisearch.py
from unittest.mock import MagicMock, patch
import pytest
from datetime import date

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
