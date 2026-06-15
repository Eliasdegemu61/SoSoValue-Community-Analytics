from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import requests

from .config import load_env, require_env
from .date_utils import utc_yesterday
from .supabase_store import get_supabase, upsert_source_run, upsert_table


load_env()

XAI_API_KEY = require_env("XAI_API_KEY")


def normalize_x_summary(summary: dict | None) -> dict:
    base = {
        "sosovalue": "No significant mentions found.",
        "sodex": "No significant mentions found.",
        "ssi": "No significant mentions found.",
    }
    if not isinstance(summary, dict):
        return base
    for key in list(base.keys()):
        value = summary.get(key)
        if isinstance(value, str) and value.strip():
            base[key] = value.strip()
    return base


def normalize_x_questions(questions: dict | None) -> dict:
    base = {
        "sosovalue": [],
        "sodex": [],
        "ssi": [],
    }
    if not isinstance(questions, dict):
        return base
    for key in list(base.keys()):
        value = questions.get(key)
        if isinstance(value, list):
            base[key] = [str(item).strip() for item in value if str(item).strip()]
    return base


def build_x_report() -> dict:
    target = utc_yesterday()
    start_dt = datetime.fromisoformat(target.iso_date)
    until_dt = start_dt + timedelta(days=1)
    since_s = start_dt.strftime("%Y-%m-%d")
    until_s = until_dt.strftime("%Y-%m-%d")

    combined_query = (
        f'("SoSoValue" OR "Sodex" OR "SSI Index") '
        f"since:{since_s} until:{until_s} "
        "-from:sosovaluecrypto -from:SOSOVALUE -from:SODEXOFFICIAL "
        "-from:sosovalue_cn -from:sosovalueJP -from:sosovalueVN"
    )

    xai_url = "https://api.x.ai/v1/responses"
    xai_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {XAI_API_KEY}",
    }
    xai_payload = {
        "model": "grok-4-1-fast-non-reasoning",
        "input": [
            {
                "role": "system",
                "content": (
                    "You are an expert crypto data analyst. You MUST use x_search to find real X data. "
                    "Return ONLY strictly valid JSON with keys summary, top_questions, and top_engaged_posts. "
                    "The summary object MUST contain non-empty strings for sosovalue, sodex, and ssi. "
                    "Each summary should be at least 2 to 4 sentences. "
                    "If a topic truly has no relevant data, write exactly 'No significant mentions found.' "
                    "The top_questions object MUST contain arrays for sosovalue, sodex, and ssi. "
                    "top_engaged_posts must be an array of objects with username, post_content, engagement, post_link, and date."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Search X for this query: {combined_query}\n\n"
                    "Perform community sentiment analysis for SoSoValue, SoDex, and SSI Index separately. "
                    "Extract the top user questions for each topic. "
                    "Identify at least 3 real post URLs. "
                    "Do not leave the summary fields empty."
                ),
            },
        ],
        "tools": [{"type": "x_search"}],
    }

    try:
        api_res = requests.post(xai_url, headers=xai_headers, json=xai_payload, timeout=60)
        api_res.raise_for_status()
        res_json = api_res.json()

        content = ""
        for item in res_json.get("output", []):
            if isinstance(item, dict) and "content" in item:
                for sub_item in item["content"]:
                    if isinstance(sub_item, dict) and sub_item.get("type") == "output_text":
                        content = sub_item.get("text", "")

        if not content:
            raise RuntimeError("Could not extract JSON content from xAI response.")

        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("\n", 1)[0].strip()

        data = json.loads(content)
    except Exception as exc:
        data = {
            "summary": {
                "sosovalue": f"X analysis unavailable for this run: {exc}",
                "sodex": f"X analysis unavailable for this run: {exc}",
                "ssi": f"X analysis unavailable for this run: {exc}",
            },
            "top_questions": {
                "sosovalue": [],
                "sodex": [],
                "ssi": [],
            },
            "top_engaged_posts": [],
            "ai_error": str(exc),
        }
    if "top_engaged_posts" not in data:
        fallback_key = next(
            (
                key
                for key in data.keys()
                if "top" in key.lower() and "post" in key.lower()
            ),
            None,
        )
        data["top_engaged_posts"] = data.get(fallback_key, [])
    data["summary"] = normalize_x_summary(data.get("summary"))
    data["top_questions"] = normalize_x_questions(data.get("top_questions"))
    data["timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    data["metadata"] = {"report_date": target.iso_date}
    return data


def persist_x_report(report: dict) -> None:
    supabase = get_supabase()
    report_date = report["metadata"]["report_date"]
    source_run = upsert_source_run(
        supabase,
        source_type="x_daily",
        community=None,
        report_date=report_date,
        schedule_basis="utc",
        raw_payload=report,
    )
    upsert_table(
        supabase,
        "x_daily_reports",
        {
            "source_run_id": source_run["id"],
            "report_date": report_date,
            "summary": report.get("summary", {}),
            "top_questions": report.get("top_questions", {}),
            "top_engaged_posts": report.get("top_engaged_posts", []),
            "captured_at": report.get("timestamp"),
            "raw_payload": report,
        },
        "report_date",
    )


def main() -> None:
    report = build_x_report()
    persist_x_report(report)
    print(f"Saved X daily report for {report['metadata']['report_date']} to Supabase.")


if __name__ == "__main__":
    main()
