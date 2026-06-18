from __future__ import annotations

import json
from google import genai

from .config import load_env, require_env
from .date_utils import singapore_yesterday
from .supabase_store import fetch_discord_reports_window, get_supabase, upsert_source_run, upsert_table


load_env()

GEMINI_API_KEY = require_env("GEMINI_API_KEY")
GEMINI_RETRIES = 1


def normalize_category(value: str) -> str:
    raw = (value or "").strip().lower()
    if "retail" in raw:
        return "retail"
    if "trading" in raw:
        return "trading"
    if "ticket" in raw or "support" in raw:
        return "tickets"
    if "dev" in raw:
        return "dev"
    return "retail"


def normalize_action_type(value: str) -> str:
    raw = (value or "").strip().lower()
    if raw == "communicate":
        return "communicate"
    return "resolve"


def generate_suggestions(gemini_client: genai.Client, prompt: str, weekly_reports: list[dict]) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, GEMINI_RETRIES + 1):
        try:
            print(f"Gemini weekly suggestions attempt {attempt}/{GEMINI_RETRIES}...")
            response = gemini_client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=f"{prompt}\n\nDATA:\n{json.dumps(weekly_reports, indent=2)}",
                config={"response_mime_type": "application/json"},
            )
            payload = json.loads(response.text)
            if not isinstance(payload.get("team_suggestions"), list) or not payload["team_suggestions"]:
                raise ValueError("Gemini returned empty weekly suggestions.")
            return payload
        except Exception as exc:
            last_error = exc
            print(f"Gemini weekly suggestions attempt {attempt} failed: {exc}")
    return {
        "team_suggestions": [
            {
                "category": "tickets",
                "action_point": f"Review the latest Discord questions manually because AI suggestions were unavailable: {last_error}",
                "action_type": "resolve",
            }
        ],
        "ai_error": str(last_error),
    }


def build_weekly_suggestions() -> dict:
    target = singapore_yesterday()
    supabase = get_supabase()
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    weekly_reports = fetch_discord_reports_window(supabase, target.iso_date, limit=7)
    if len(weekly_reports) < 1:
        raise RuntimeError("No Discord daily reports found in Supabase for weekly suggestions generation.")

    prompt = """
    You are a Community Manager and Product Manager assistant.
    Analyze the following 7 days of community data covering Retail, Trading, Tickets, and Dev.

    Based ON THE SUMMARIES AND QUESTIONS provided, identify exactly 3 to 5 actionable suggestions for the core team.
    For each suggestion, define the 'action_type' as either:
    - "resolve": if it's a bug, technical issue, or missing feature the team needs to fix.
    - "communicate": if it's an educational gap where the team needs to post an announcement, FAQ, or clarify rules.

    The 'category' MUST be exactly one of:
    - "retail"
    - "trading"
    - "tickets"
    - "dev"

    Return ONLY a valid JSON object in this exact format:
    {
      "team_suggestions": [
        {
          "category": "[retail, trading, tickets, or dev]",
          "action_point": "[The actionable suggestion]",
          "action_type": "[resolve or communicate]"
        }
      ]
    }
    """

    payload = generate_suggestions(gemini_client, prompt, weekly_reports)

    normalized_items = []
    for item in payload.get("team_suggestions", []):
        if not isinstance(item, dict):
            continue
        normalized_items.append(
            {
                "category": normalize_category(str(item.get("category", ""))),
                "action_point": str(item.get("action_point", "")).strip(),
                "action_type": normalize_action_type(str(item.get("action_type", ""))),
            }
        )
    payload["team_suggestions"] = normalized_items
    payload["metadata"] = {"report_date": target.iso_date, "days_used": len(weekly_reports)}
    return payload


def persist_weekly_suggestions(payload: dict) -> None:
    supabase = get_supabase()
    report_date = payload["metadata"]["report_date"]
    source_run = upsert_source_run(
        supabase,
        source_type="weekly_suggestions",
        community=None,
        report_date=report_date,
        schedule_basis="asia_singapore",
        raw_payload=payload,
    )
    upsert_table(
        supabase,
        "weekly_suggestions",
        {
            "source_run_id": source_run["id"],
            "report_date": report_date,
            "team_suggestions": payload["team_suggestions"],
            "raw_payload": payload,
        },
        "report_date",
    )


def main() -> None:
    payload = build_weekly_suggestions()
    persist_weekly_suggestions(payload)
    print(f"Saved weekly suggestions for {payload['metadata']['report_date']} to Supabase.")


if __name__ == "__main__":
    main()
