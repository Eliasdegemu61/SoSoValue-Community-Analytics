from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from supabase import Client, create_client

from .config import load_env, require_env


load_env()


def get_supabase() -> Client:
    url = require_env("SUPABASE_URL")
    key = require_env("SUPABASE_SECRET_KEY")
    parsed = urlparse(url)
    if not parsed.scheme.startswith("http"):
        raise RuntimeError(
            "SUPABASE_URL must start with http:// or https://."
        )
    host = parsed.netloc.lower()
    if "dashboard.supabase.com" in host or host.endswith("supabase.com") and ".supabase.co" not in host:
        raise RuntimeError(
            "SUPABASE_URL looks like a dashboard/site URL, not a project API URL. "
            "Use the project URL from Supabase, usually like https://<project-ref>.supabase.co"
        )
    return create_client(url, key)


def upsert_source_run(
    supabase: Client,
    *,
    source_type: str,
    community: str | None,
    report_date: str,
    schedule_basis: str,
    raw_payload: dict[str, Any],
    status: str = "completed",
    error_message: str | None = None,
) -> dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    row = {
        "source_type": source_type,
        "community": community,
        "report_date": report_date,
        "schedule_basis": schedule_basis,
        "status": status,
        "raw_payload": raw_payload,
        "started_at": now_iso,
        "completed_at": now_iso if status == "completed" else None,
        "error_message": error_message,
        "updated_at": now_iso,
    }
    result = (
        supabase.table("source_runs")
        .upsert(row, on_conflict="source_type,community,report_date")
        .execute()
    )
    return result.data[0]


def upsert_table(
    supabase: Client,
    table_name: str,
    row: dict[str, Any],
    conflict_column: str,
) -> dict[str, Any]:
    result = supabase.table(table_name).upsert(row, on_conflict=conflict_column).execute()
    return result.data[0]


def fetch_discord_reports_window(supabase: Client, end_date: str, limit: int = 7) -> list[dict[str, Any]]:
    result = (
        supabase.table("discord_daily_reports")
        .select("report_date,reports")
        .lte("report_date", end_date)
        .order("report_date", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []
