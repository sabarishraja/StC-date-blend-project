# server/query_engine.py
import os
from dotenv import load_dotenv
import anthropic
from supabase import create_client
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["POST"], allow_headers=["*"])

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

SCHEMA_DESCRIPTION = """
You have access to a PostgreSQL database with these tables:

ga4_page_metrics (date DATE, page_path TEXT, landing_page TEXT, source_medium TEXT, screen_class TEXT,
  sessions INT, total_users INT, new_users INT, engaged_sessions INT,
  avg_engagement_time_sec NUMERIC, bounce_rate NUMERIC, screenpage_views INT)

gsc_queries (date DATE, query TEXT, page TEXT, country TEXT, device TEXT,
  clicks INT, impressions INT, ctr NUMERIC, position NUMERIC)

gsc_pages (date DATE, page TEXT, clicks INT, impressions INT, ctr NUMERIC, position NUMERIC)

ms_top_searches (date DATE, query_term TEXT, search_count INT)

ms_no_results (date DATE, query_term TEXT, search_count INT)

ms_countries (date DATE, country_code TEXT, search_count INT)

Key joins:
- gsc_queries.query ≈ ms_top_searches.query_term (use LOWER() for case-insensitive match)
- gsc_queries.page path segment ≈ ga4_page_metrics.page_path
- GA4 data covers 12 months; Meilisearch covers only 90 days
- Use LEFT JOIN when combining Meilisearch with GSC/GA4 to preserve older records
"""

SQL_SYSTEM_PROMPT = f"""You are a SQL expert for a PostgreSQL database.
{SCHEMA_DESCRIPTION}
Rules:
- Return ONLY the SQL query, nothing else. No markdown, no explanation.
- Only write SELECT statements.
- Always include a LIMIT (max 500 rows) unless doing an aggregation.
- Use LOWER() for case-insensitive text comparisons.
- For date ranges, default to the last 90 days unless the user specifies otherwise.
"""

ANSWER_SYSTEM_PROMPT = f"""You are a helpful data analyst for SubjectToClimate, an educational nonprofit.
{SCHEMA_DESCRIPTION}
You will receive a user question and JSON rows from a database query.
Write a clear, concise plain-English answer (2-5 sentences). Highlight the most important numbers.
If the result is empty, say so and suggest why.
"""


def is_safe_sql(sql: str) -> bool:
    stripped = sql.strip().lower()
    if not stripped:
        return False
    return stripped.startswith("select")


class QuestionRequest(BaseModel):
    question: str


@app.post("/ask")
def ask(req: QuestionRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    sql_response = anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=[{"type": "text", "text": SQL_SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": question}],
    )
    sql = sql_response.content[0].text.strip()

    if not is_safe_sql(sql):
        raise HTTPException(status_code=400, detail="Generated query was not a SELECT statement")

    try:
        result = supabase_client.rpc("execute_query", {"sql_query": sql}).execute()
        rows = result.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")

    answer_response = anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=[{"type": "text", "text": ANSWER_SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"Question: {question}\n\nData: {rows}"}],
    )
    answer = answer_response.content[0].text.strip()

    return {"answer": answer, "sql": sql, "row_count": len(rows)}
