# tests/test_sync_ga4.py
from types import SimpleNamespace

def _make_row(dim_values, metric_values):
    """Creates a mock GA4 Row object matching the API's structure."""
    dims = [SimpleNamespace(value=v) for v in dim_values]
    mets = [SimpleNamespace(value=v) for v in metric_values]
    return SimpleNamespace(dimension_values=dims, metric_values=mets)

def test_build_ga4_records():
    from sync.sync_ga4 import build_records
    row = _make_row(
        dim_values=["20250401", "/resources/penguins", "/resources/penguins", "google / organic", "(not set)"],
        metric_values=["150", "200", "80", "120", "95.5", "0.12", "300"],
    )
    result = build_records([row])
    assert len(result) == 1
    assert result[0]["date"] == "2025-04-01"
    assert result[0]["page_path"] == "/resources/penguins"
    assert result[0]["landing_page"] == "/resources/penguins"
    assert result[0]["source_medium"] == "google / organic"
    assert result[0]["screen_class"] == "(not set)"
    assert result[0]["sessions"] == 150
    assert result[0]["total_users"] == 200
    assert result[0]["new_users"] == 80
    assert result[0]["engaged_sessions"] == 120
    assert result[0]["avg_engagement_time_sec"] == 95.5
    assert result[0]["bounce_rate"] == 0.12
    assert result[0]["screenpage_views"] == 300

def test_build_ga4_records_empty():
    from sync.sync_ga4 import build_records
    assert build_records([]) == []

def test_format_date():
    from sync.sync_ga4 import format_ga4_date
    assert format_ga4_date("20250401") == "2025-04-01"
    assert format_ga4_date("20251231") == "2025-12-31"
