# tests/test_query_engine.py

def test_is_safe_select_passes():
    from server.query_engine import is_safe_sql
    assert is_safe_sql("SELECT * FROM ms_top_searches LIMIT 10") is True
    assert is_safe_sql("  select count(*) from gsc_queries  ") is True

def test_is_safe_blocks_writes():
    from server.query_engine import is_safe_sql
    assert is_safe_sql("DROP TABLE ms_top_searches") is False
    assert is_safe_sql("DELETE FROM gsc_queries") is False
    assert is_safe_sql("INSERT INTO gsc_queries VALUES (1)") is False
    assert is_safe_sql("UPDATE gsc_queries SET clicks = 0") is False

def test_is_safe_blocks_empty():
    from server.query_engine import is_safe_sql
    assert is_safe_sql("") is False
    assert is_safe_sql("   ") is False
