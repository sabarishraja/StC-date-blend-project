# server/query_engine.py
import os
import logging
from dotenv import load_dotenv
import anthropic
from supabase import create_client
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

SCHEMA_DESCRIPTION = """
You have access to a PostgreSQL database with these tables:

ga4_page_metrics (date DATE, page_path TEXT, landing_page TEXT, source_medium TEXT,
  sessions INT, total_users INT, new_users INT, engaged_sessions INT,
  avg_engagement_time_sec NUMERIC, bounce_rate NUMERIC, screenpage_views INT)

gsc_queries (date DATE, query TEXT, page TEXT, country TEXT, device TEXT,
  clicks INT, impressions INT, ctr NUMERIC, position NUMERIC)

gsc_pages (date DATE, page TEXT, clicks INT, impressions INT, ctr NUMERIC, position NUMERIC)

ms_top_searches (date DATE, query_term TEXT, search_count INT)

ms_no_results (date DATE, query_term TEXT, search_count INT)

ms_countries (date DATE, country_code TEXT, search_count INT)

fs_page_metrics (date DATE, page_url TEXT, total_sessions INT, avg_scroll_depth NUMERIC,
  avg_active_time_sec NUMERIC, rage_clicks INT, dead_clicks INT)

Key joins:
- gsc_queries.query ≈ ms_top_searches.query_term (use LOWER() for case-insensitive match)
- gsc_queries.page path segment ≈ ga4_page_metrics.page_path
- ga4_page_metrics.page_path ≈ fs_page_metrics.page_url
- GA4 data covers 12 months; Meilisearch and Fullstory cover only 90 days
- Use LEFT JOIN when combining Meilisearch or Fullstory with GSC/GA4 to preserve older records
"""

SQL_SYSTEM_PROMPT = f"""You are a SQL expert for a PostgreSQL database.
{SCHEMA_DESCRIPTION}
Rules:
- Return ONLY the SQL query, nothing else. No markdown, no explanation.
- Only write SELECT statements.
- Always include a LIMIT (max 500 rows) unless doing an aggregation.
- Use LOWER() for case-insensitive text comparisons.
- For date ranges, default to the last 90 days. Always calculate relative dates using the maximum date in the queried table (e.g., date >= (SELECT MAX(date) FROM target_table) - 90) instead of CURRENT_DATE.

Performance rules — CRITICAL, always follow these to avoid query timeouts:
1. TRAFFIC CHANNEL QUESTIONS: To answer how users found a page (search vs direct vs referral vs social),
   use the source_medium column in ga4_page_metrics with a CASE expression — do NOT join gsc_queries or gsc_pages.
   Example bucket logic:
     CASE
       WHEN LOWER(source_medium) LIKE '%organic%' THEN 'Organic Search'
       WHEN LOWER(source_medium) LIKE '%cpc%' OR LOWER(source_medium) LIKE '%paid%' THEN 'Paid Search'
       WHEN LOWER(source_medium) = 'direct / (none)' THEN 'Direct / Navigation'
       WHEN LOWER(source_medium) LIKE '%social%' OR LOWER(source_medium) LIKE '%instagram%'
            OR LOWER(source_medium) LIKE '%facebook%' OR LOWER(source_medium) LIKE '%twitter%'
            OR LOWER(source_medium) LIKE '%linkedin%' THEN 'Social'
       WHEN LOWER(source_medium) LIKE '%email%' THEN 'Email'
       ELSE 'Referral / Other'
     END AS channel
2. CROSS-TABLE JOINS: Always pre-aggregate each table into a CTE with SUM/GROUP BY before joining.
   Never join two large tables at the row level. Example pattern:
     WITH ga4 AS (SELECT page_path, SUM(sessions) AS sessions FROM ga4_page_metrics WHERE ... GROUP BY page_path),
          gsc  AS (SELECT page, SUM(clicks) AS clicks FROM gsc_pages WHERE ... GROUP BY page)
     SELECT ... FROM ga4 LEFT JOIN gsc ON ...
3. DATE FILTER FIRST: Apply the date WHERE clause inside every CTE or subquery — never filter after a join.
4. AVOID large row-level joins: Never do FROM ga4_page_metrics JOIN gsc_queries without a CTE wrapping both sides first.
"""

ANSWER_SYSTEM_PROMPT = f"""You are a helpful data analyst for SubjectToClimate, an educational nonprofit.
{SCHEMA_DESCRIPTION}
You will receive a user question and JSON rows from a database query.
Write a clear, concise plain-English answer (2-5 sentences). Highlight the most important numbers.
If the result is empty, say so and suggest why.
"""


INSIGHTS_QUERIES = {
    "traffic_trend": """
        SELECT
            SUM(CASE WHEN date >= (SELECT MAX(date) FROM ga4_page_metrics) - 7 THEN sessions ELSE 0 END) AS sessions_this_week,
            SUM(CASE WHEN date >= (SELECT MAX(date) FROM ga4_page_metrics) - 14 AND date < (SELECT MAX(date) FROM ga4_page_metrics) - 7 THEN sessions ELSE 0 END) AS sessions_last_week
        FROM ga4_page_metrics
        WHERE date >= (SELECT MAX(date) FROM ga4_page_metrics) - 14
    """,
    "top_pages": """
        SELECT page_path, SUM(sessions) AS sessions, SUM(screenpage_views) AS views
        FROM ga4_page_metrics
        WHERE date >= (SELECT MAX(date) FROM ga4_page_metrics) - 7
        GROUP BY page_path
        ORDER BY sessions DESC
        LIMIT 5
    """,
    "top_searches": """
        SELECT query_term, SUM(search_count) AS total
        FROM ms_top_searches
        WHERE date >= (SELECT MAX(date) FROM ms_top_searches) - 7
        GROUP BY query_term
        ORDER BY total DESC
        LIMIT 5
    """,
    "content_gaps": """
        SELECT query_term, SUM(search_count) AS total
        FROM ms_no_results
        WHERE date >= (SELECT MAX(date) FROM ms_no_results) - 7
        GROUP BY query_term
        ORDER BY total DESC
        LIMIT 5
    """,
    "gsc_opportunities": """
        SELECT query, SUM(impressions) AS impressions, SUM(clicks) AS clicks,
               ROUND(AVG(ctr)::numeric, 4) AS avg_ctr
        FROM gsc_queries
        WHERE date >= (SELECT MAX(date) FROM gsc_queries) - 7
        GROUP BY query
        HAVING SUM(impressions) > 50
        ORDER BY impressions DESC, avg_ctr ASC
        LIMIT 5
    """,
}

INSIGHTS_SYSTEM_PROMPT = f"""You are a data analyst for SubjectToClimate, an educational nonprofit focused on climate content.
{SCHEMA_DESCRIPTION}
You will receive data from 5 queries run against the analytics database.
Generate exactly 5 short insight cards. Each card must be one sentence (max 25 words), factual, and highlight the single most important number or trend.
Return a JSON array of objects: [{{"title": "short label", "insight": "one sentence", "type": "positive|negative|neutral"}}]
Use "positive" for good trends, "negative" for gaps or drops, "neutral" for informational.
Return ONLY valid JSON. No markdown, no explanation."""


def _run_insights_query(sql: str, key: str = ""):
    try:
        result = supabase_client.rpc("execute_query", {"sql_query": sql.strip()}).execute()
        rows = result.data or []
        logging.info("[insights:%s] returned %d rows", key, len(rows))
        return rows
    except Exception as e:
        logging.error("[insights:%s] query failed: %s", key, e)
        return []


def is_safe_sql(sql: str) -> bool:
    stripped = sql.strip().lower()
    if not stripped:
        return False
    return stripped.startswith("select")


class HistoryMessage(BaseModel):
    role: str   # "user" or "assistant"
    content: str


class QuestionRequest(BaseModel):
    question: str
    history: list[HistoryMessage] = []


SOURCE_TABLE_MAP = {
    "ga4_page_metrics": "GA4",
    "gsc_queries": "GSC",
    "gsc_pages": "GSC",
    "ms_top_searches": "Meilisearch",
    "ms_no_results": "Meilisearch",
    "ms_countries": "Meilisearch",
    "fs_page_metrics": "FullStory",
}


def detect_sources(sql: str) -> list[str]:
    """Return the deduplicated friendly source names referenced in the SQL."""
    sql_lower = sql.lower()
    seen = []
    for table, label in SOURCE_TABLE_MAP.items():
        if table in sql_lower and label not in seen:
            seen.append(label)
    return seen


@app.post("/ask")
def ask(req: QuestionRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Build the conversation history for the SQL generation call.
    # History contains prior (question, sql) pairs so Claude has context for follow-ups.
    sql_messages = []
    for msg in req.history:
        sql_messages.append({"role": msg.role, "content": msg.content})
    sql_messages.append({"role": "user", "content": question})

    sql_response = anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=[{"type": "text", "text": SQL_SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}}],
        messages=sql_messages,
    )
    sql = sql_response.content[0].text.strip()
    # Strip markdown code fences if present
    if sql.startswith("```"):
        sql = sql.split("\n", 1)[-1]
        sql = sql.rsplit("```", 1)[0]
    # Take only the first statement — drops any trailing semicolons, comments, or extra statements
    sql = sql.split(";")[0].strip()

    if not is_safe_sql(sql):
        raise HTTPException(status_code=400, detail="Generated query was not a SELECT statement")

    try:
        result = supabase_client.rpc("execute_query", {"sql_query": sql}).execute()
        rows = result.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")

    # Build answer history: include prior exchanges so the analyst answer is coherent
    answer_messages = []
    for msg in req.history:
        answer_messages.append({"role": msg.role, "content": msg.content})
    answer_messages.append({
        "role": "user",
        "content": f"Question: {question}\n\nData: {rows}"
    })

    answer_response = anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=[{"type": "text", "text": ANSWER_SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}}],
        messages=answer_messages,
    )
    answer = answer_response.content[0].text.strip()
    data_sources = detect_sources(sql)

    return {
        "answer": answer,
        "sql": sql,
        "row_count": len(rows),
        "data_sources": data_sources,
    }


@app.get("/debug/queries")
def debug_queries():
    """Returns raw row counts and any errors from each insights query — no Claude involved."""
    results = {}
    for key, sql in INSIGHTS_QUERIES.items():
        try:
            result = supabase_client.rpc("execute_query", {"sql_query": sql.strip()}).execute()
            rows = result.data or []
            results[key] = {"row_count": len(rows), "sample": rows[:2], "error": None}
        except Exception as e:
            results[key] = {"row_count": 0, "sample": [], "error": str(e)}
    return results


@app.get("/insights")
def get_insights():
    import json
    data = {key: _run_insights_query(sql, key) for key, sql in INSIGHTS_QUERIES.items()}

    response = anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        system=[{"type": "text", "text": INSIGHTS_SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"Analytics data: {json.dumps(data, default=str)}"}],
    )

    try:
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0].strip()
        insights = json.loads(raw)
    except Exception:
        insights = []

    return {"insights": insights}
