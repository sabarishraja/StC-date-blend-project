-- ga4_page_metrics: daily GA4 page performance
CREATE TABLE IF NOT EXISTS ga4_page_metrics (
    id          BIGSERIAL PRIMARY KEY,
    date        DATE    NOT NULL,
    page_path   TEXT    NOT NULL,
    landing_page TEXT   NOT NULL DEFAULT '',
    source_medium TEXT  NOT NULL DEFAULT '',
    sessions              INTEGER DEFAULT 0,
    total_users           INTEGER DEFAULT 0,
    new_users             INTEGER DEFAULT 0,
    engaged_sessions      INTEGER DEFAULT 0,
    avg_engagement_time_sec NUMERIC DEFAULT 0,
    bounce_rate           NUMERIC DEFAULT 0,
    screenpage_views      INTEGER DEFAULT 0,
    UNIQUE (date, page_path, source_medium, landing_page)
);

-- gsc_queries: Search Console query-level data
CREATE TABLE IF NOT EXISTS gsc_queries (
    id          BIGSERIAL PRIMARY KEY,
    date        DATE    NOT NULL,
    query       TEXT    NOT NULL,
    page        TEXT    NOT NULL DEFAULT '',
    country     TEXT    NOT NULL DEFAULT '',
    device      TEXT    NOT NULL DEFAULT '',
    clicks      INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    ctr         NUMERIC DEFAULT 0,
    position    NUMERIC DEFAULT 0,
    UNIQUE (date, query, page, country, device)
);

-- gsc_pages: Search Console page-level aggregates
CREATE TABLE IF NOT EXISTS gsc_pages (
    id          BIGSERIAL PRIMARY KEY,
    date        DATE    NOT NULL,
    page        TEXT    NOT NULL,
    clicks      INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    ctr         NUMERIC DEFAULT 0,
    position    NUMERIC DEFAULT 0,
    UNIQUE (date, page)
);

-- ms_top_searches: Meilisearch top queried terms
CREATE TABLE IF NOT EXISTS ms_top_searches (
    id           BIGSERIAL PRIMARY KEY,
    date         DATE NOT NULL,
    query_term   TEXT NOT NULL,
    search_count INTEGER DEFAULT 0,
    UNIQUE (date, query_term)
);

-- ms_no_results: Meilisearch queries that returned nothing
CREATE TABLE IF NOT EXISTS ms_no_results (
    id           BIGSERIAL PRIMARY KEY,
    date         DATE NOT NULL,
    query_term   TEXT NOT NULL,
    search_count INTEGER DEFAULT 0,
    UNIQUE (date, query_term)
);

-- ms_countries: Meilisearch searches by country
CREATE TABLE IF NOT EXISTS ms_countries (
    id           BIGSERIAL PRIMARY KEY,
    date         DATE NOT NULL,
    country_code TEXT NOT NULL,
    search_count INTEGER DEFAULT 0,
    UNIQUE (date, country_code)
);

-- fs_page_metrics: FullStory aggregated metrics per page (from UI CSV export)
CREATE TABLE IF NOT EXISTS fs_page_metrics (
    id              BIGSERIAL PRIMARY KEY,
    date            DATE NOT NULL,
    page_url        TEXT NOT NULL,
    total_sessions  INTEGER DEFAULT 0,
    avg_scroll_depth NUMERIC DEFAULT 0,
    avg_active_time_sec NUMERIC DEFAULT 0,
    rage_clicks     INTEGER DEFAULT 0,
    dead_clicks     INTEGER DEFAULT 0,
    UNIQUE (date, page_url)
);

-- Read-only role for AI query layer
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'readonly_ai') THEN
        CREATE ROLE readonly_ai;
    END IF;
END
$$;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_ai;

-- RPC function: AI layer calls this to execute SELECT queries safely
CREATE OR REPLACE FUNCTION execute_query(sql_query text)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    result json;
BEGIN
    IF NOT (lower(trim(sql_query)) LIKE 'select%') THEN
        RAISE EXCEPTION 'Only SELECT queries are allowed';
    END IF;
    EXECUTE 'SELECT json_agg(t) FROM (' || sql_query || ') t' INTO result;
    RETURN COALESCE(result, '[]'::json);
END;
$$;
