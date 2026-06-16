from __future__ import annotations

import json
import time

from google import genai

from .config import load_env, require_env
from .date_utils import singapore_yesterday
from .supabase_store import fetch_discord_reports_window, get_supabase, upsert_source_run, upsert_table


load_env()

GEMINI_API_KEY = require_env("GEMINI_API_KEY")
GEMINI_RETRIES = 3


def normalize_reports(value: dict) -> dict:
    reports = {
        "retail": {"summary": "", "questions": []},
        "trading": {"summary": "", "questions": []},
        "tickets": {"summary": "", "questions": []},
        "dev": {"summary": "", "questions": []},
    }
    if not isinstance(value, dict):
        return reports
    for key, section in value.items():
        raw_key = str(key).lower()
        if "retail" in raw_key:
            normalized_key = "retail"
        elif "trading" in raw_key:
            normalized_key = "trading"
        elif "ticket" in raw_key or "support" in raw_key:
            normalized_key = "tickets"
        elif "dev" in raw_key:
            normalized_key = "dev"
        else:
            continue
        if not isinstance(section, dict):
            continue
        questions = section.get("questions", [])
        reports[normalized_key] = {
            "summary": str(section.get("summary", "")).strip(),
            "questions": questions if isinstance(questions, list) else [],
        }
    return reports


def has_useful_reports(reports: dict) -> bool:
    return any(
        bool(section.get("summary", "").strip()) or bool(section.get("questions"))
        for section in reports.values()
        if isinstance(section, dict)
    )


def generate_weekly_report(client: genai.Client, prompt: str, data_list: list[dict]) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, GEMINI_RETRIES + 1):
        try:
            print(f"Gemini weekly report attempt {attempt}/{GEMINI_RETRIES}...")
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=[prompt, json.dumps(data_list)],
                config={"response_mime_type": "application/json"},
            )
            weekly_report = json.loads(response.text)
            weekly_report["reports"] = normalize_reports(weekly_report.get("reports", {}))
            if not has_useful_reports(weekly_report["reports"]):
                raise ValueError("Gemini returned empty weekly reports.")
            return weekly_report
        except Exception as exc:
            last_error = exc
            print(f"Gemini weekly report attempt {attempt} failed: {exc}")
            if attempt < GEMINI_RETRIES:
                time.sleep(20 * attempt)
    raise RuntimeError(f"Gemini weekly report failed after {GEMINI_RETRIES} attempts: {last_error}")


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
    weekly_report = generate_weekly_report(client, prompt, data_list)
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
