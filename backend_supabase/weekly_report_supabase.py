from __future__ import annotations

import json

from google import genai

from .config import load_env, require_env
from .date_utils import singapore_yesterday
from .supabase_store import fetch_discord_reports_window, get_supabase, upsert_source_run, upsert_table


load_env()

GEMINI_API_KEY = require_env("GEMINI_API_KEY")


def build_weekly_report() -> dict:
    target = singapore_yesterday()
    supabase = get_supabase()
    client = genai.Client(api_key=GEMINI_API_KEY)
    data_list = fetch_discord_reports_window(supabase, target.iso_date, limit=7)
    if len(data_list) < 1:
        raise RuntimeError("No Discord daily reports found in Supabase for weekly report generation.")

    prompt = (
        "Analyze these 7 days of community data. Return JSON with a 'reports' object. "
        "It must contain retail, trading, tickets, and dev. "
        "Each section must have 'summary' and 'questions'."
    )
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[prompt, json.dumps(data_list)],
            config={"response_mime_type": "application/json"},
        )
        weekly_report = json.loads(response.text)
    except Exception as exc:
        weekly_report = {
            "reports": {
                "retail": {"summary": f"AI weekly summary unavailable for this run: {exc}", "questions": []},
                "trading": {"summary": f"AI weekly summary unavailable for this run: {exc}", "questions": []},
                "tickets": {"summary": f"AI weekly summary unavailable for this run: {exc}", "questions": []},
                "dev": {"summary": f"AI weekly summary unavailable for this run: {exc}", "questions": []},
            },
            "ai_error": str(exc),
        }
    weekly_report["metadata"] = {"report_date": target.iso_date, "days_used": len(data_list)}
    return weekly_report


def persist_weekly_report(report: dict) -> None:
    supabase = get_supabase()
    report_date = report["metadata"]["report_date"]
    source_run = upsert_source_run(
        supabase,
        source_type="weekly_report",
        community=None,
        report_date=report_date,
        schedule_basis="asia_singapore",
        raw_payload=report,
    )
    upsert_table(
        supabase,
        "weekly_reports",
        {
            "source_run_id": source_run["id"],
            "report_date": report_date,
            "reports": report["reports"],
            "raw_payload": report,
        },
        "report_date",
    )


def main() -> None:
    report = build_weekly_report()
    persist_weekly_report(report)
    print(f"Saved weekly report for {report['metadata']['report_date']} to Supabase.")


if __name__ == "__main__":
    main()
