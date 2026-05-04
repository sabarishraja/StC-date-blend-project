def test_build_query_records():
    from sync.sync_gsc import build_query_records
    raw_rows = [
        {"keys": ["penguins", "https://stc.org/resources/penguins", "usa", "MOBILE"],
         "clicks": 45, "impressions": 890, "ctr": 0.0506, "position": 3.2},
    ]
    result = build_query_records("2025-04-01", raw_rows)
    assert result == [{
        "date": "2025-04-01",
        "query": "penguins",
        "page": "https://stc.org/resources/penguins",
        "country": "usa",
        "device": "MOBILE",
        "clicks": 45,
        "impressions": 890,
        "ctr": 0.0506,
        "position": 3.2,
    }]

def test_build_page_records():
    from sync.sync_gsc import build_page_records
    raw_rows = [
        {"keys": ["https://stc.org/resources/penguins"],
         "clicks": 120, "impressions": 2400, "ctr": 0.05, "position": 3.1},
    ]
    result = build_page_records("2025-04-01", raw_rows)
    assert result == [{
        "date": "2025-04-01",
        "page": "https://stc.org/resources/penguins",
        "clicks": 120,
        "impressions": 2400,
        "ctr": 0.05,
        "position": 3.1,
    }]

def test_build_query_records_empty():
    from sync.sync_gsc import build_query_records
    assert build_query_records("2025-04-01", []) == []
