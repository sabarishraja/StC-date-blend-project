"""CSV upload endpoints for non-technical users to ingest FullStory and
Meilisearch exports from the browser. See
docs/superpowers/specs/2026-05-20-csv-upload-ui-design.md.
"""

from __future__ import annotations

import csv
import io
import logging
import os

from dotenv import load_dotenv
from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from supabase import create_client

load_dotenv()

from sync.loaders import (
    LoadResult,
    load_fullstory_dataframe,
    load_meilisearch_dataframe,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])

UPLOAD_PASSWORD = os.environ.get("UPLOAD_PASSWORD", "")
UPLOAD_MAX_MB = int(os.environ.get("UPLOAD_MAX_MB", "50"))
MAX_BYTES = UPLOAD_MAX_MB * 1024 * 1024

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)


def _check_password(x_upload_password: str | None) -> None:
    if not UPLOAD_PASSWORD:
        raise HTTPException(
            status_code=500,
            detail="UPLOAD_PASSWORD is not configured on the server.",
        )
    if x_upload_password != UPLOAD_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid upload password")


async def _read_csv_rows(file: UploadFile) -> list[dict]:
    contents = await file.read()
    if len(contents) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File {file.filename} exceeds the {UPLOAD_MAX_MB} MB limit.",
        )
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = contents.decode("latin-1")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Cannot decode CSV: {e}")
    try:
        reader = csv.DictReader(io.StringIO(text))
        return list(reader)
    except csv.Error as e:
        raise HTTPException(status_code=400, detail=f"CSV parse error: {e}")


def _result_to_dict(result: LoadResult) -> dict:
    return {
        "source": result.source,
        "filename": result.filename,
        "table": result.table,
        "rows_read": result.rows_read,
        "rows_written": result.rows_written,
        "date_range": list(result.date_range) if result.date_range else None,
        "errors": result.errors,
        "ok": result.ok,
    }


@router.post("/fullstory")
async def upload_fullstory(
    file: UploadFile = File(...),
    x_upload_password: str | None = Header(default=None),
):
    _check_password(x_upload_password)
    rows = await _read_csv_rows(file)

    result = load_fullstory_dataframe(rows, file.filename or "fullstory.csv", supabase_client)
    log.info(
        "upload fullstory file=%s rows_read=%d rows_written=%d errors=%s",
        file.filename, result.rows_read, result.rows_written, result.errors,
    )
    return {"results": [_result_to_dict(result)]}


@router.post("/meilisearch")
async def upload_meilisearch(
    files: list[UploadFile] = File(...),
    x_upload_password: str | None = Header(default=None),
):
    _check_password(x_upload_password)
    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded.")

    results: list[dict] = []
    for f in files:
        try:
            rows = await _read_csv_rows(f)
        except HTTPException as e:
            results.append({
                "source": "meilisearch",
                "filename": f.filename,
                "table": None,
                "rows_read": 0,
                "rows_written": 0,
                "date_range": None,
                "errors": [e.detail],
                "ok": False,
            })
            continue

        result = load_meilisearch_dataframe(rows, f.filename or "meilisearch.csv", supabase_client)
        log.info(
            "upload meilisearch file=%s table=%s rows_read=%d rows_written=%d errors=%s",
            f.filename, result.table, result.rows_read, result.rows_written, result.errors,
        )
        results.append(_result_to_dict(result))

    return {"results": results}
