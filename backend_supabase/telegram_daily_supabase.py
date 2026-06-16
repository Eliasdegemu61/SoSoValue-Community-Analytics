from __future__ import annotations

import asyncio
import json
from collections import Counter
from datetime import datetime, timezone

from google import genai
from telethon import TelegramClient
from telethon.sessions import StringSession

from .config import load_env, require_env
from .date_utils import SINGAPORE_TZ, singapore_yesterday
from .supabase_store import get_supabase, upsert_source_run, upsert_table


load_env()

API_ID = int(require_env("TELEGRAM_API_ID"))
API_HASH = require_env("TELEGRAM_API_HASH")
GEMINI_API_KEY = require_env("GEMINI_API_KEY")
TELEGRAM_STRING_SESSION = require_env("TELEGRAM_STRING_SESSION").strip()

CHAT_ID = "sosovaluecommunity"
DEFAULT_COMMUNITY = "SOSOVALUE"
MAX_TELEGRAM_MESSAGES = 10000
GEMINI_TIMEOUT_SECONDS = 90

SECTION_NAMES = {
    "1": "General",
    "15160": "Indonesia",
    "23184": "Tieng Viet",
    "20990": "Applications/Proposal",
    "30979": "Arabic",
    "18570": "Japanese",
    "364414": "SoSoValue Product Feedback",
    "15158": "Chinese",
    "24782": "Espanol",
    "58531": "Portugues",
    "85995": "Turkce",
}

MOD_MAPPING = {
    "1061421972": "Yucel | SoSoValue",
    "860236845": "Mick | SoSoValue",
    "6884912625": "SoSoValue Jazon",
    "1652169946": "MANJIROW | SoSoValue",
    "1920063943": "AQC Capital",
    "7447683454": "nishi",
    "820556857": "Elias",
    "6606384218": "Felix SoDEX",
    "1476578633": "0x0BKT",
}


def parse_analysis(raw: dict) -> tuple[str, list[str]]:
    return raw.get("summary", ""), raw.get("questions", [])


async def build_report(community: str = DEFAULT_COMMUNITY) -> dict:
    target = singapore_yesterday()
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    session = StringSession(TELEGRAM_STRING_SESSION)

    async with TelegramClient(session, API_ID, API_HASH) as client:
        if not await client.is_user_authorized():
            raise RuntimeError(
                "Telegram string session is missing, expired, or invalid. "
                "Regenerate TELEGRAM_STRING_SESSION locally and update the GitHub secret."
            )

        print(f"Connected to Telegram. Starting extraction for {target.iso_date}...")
        entity = await client.get_entity(CHAT_ID)
        start_win = datetime.combine(target.report_date, datetime.min.time(), tzinfo=SINGAPORE_TZ)
        end_win = datetime.combine(target.report_date, datetime.max.time().replace(microsecond=0), tzinfo=SINGAPORE_TZ)

        chat_logs_for_ai = []
        hour_counts = {datetime(2000, 1, 1, h).strftime("%I %p"): 0 for h in range(24)}
        section_counts = Counter()
        user_counts = Counter()
        total_msg_count = 0

        async for msg in client.iter_messages(entity, offset_date=end_win):
            msg_date_tz = msg.date.astimezone(SINGAPORE_TZ)
            if msg_date_tz < start_win:
                break

            total_msg_count += 1
            if total_msg_count % 500 == 0:
                print(f"Processed {total_msg_count} Telegram messages...")
            if total_msg_count >= MAX_TELEGRAM_MESSAGES:
                print(f"Reached Telegram message cap ({MAX_TELEGRAM_MESSAGES}); continuing with collected data.")
                break

            sid = "1"
            if msg.reply_to:
                raw_id = getattr(msg.reply_to, "reply_to_top_id", None)
                sid = str(raw_id) if raw_id else "1"

            txt = msg.text or ""
            if txt:
                section_name = SECTION_NAMES.get(sid, "General")
                chat_logs_for_ai.append(f"[{section_name}] {txt}")
                section_counts[section_name] += 1

            hour_counts[msg_date_tz.strftime("%I %p")] += 1
            uname = MOD_MAPPING.get(
                str(msg.sender_id),
                msg.sender.first_name if msg.sender and msg.sender.first_name else "Anon",
            )
            user_counts[uname] += 1

        ai_raw = {}
        summary = ""
        questions: list[str] = []
        if chat_logs_for_ai:
            prompt = "Analyze these Telegram messages. Return JSON with 'summary' and 'questions'."
            try:
                print(f"Sending {len(chat_logs_for_ai[-1000:])} Telegram messages to Gemini...")
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        gemini_client.models.generate_content,
                        model="gemini-3-flash-preview",
                        contents=f"{prompt}\n\nDATA:\n" + "\n".join(chat_logs_for_ai[-1000:]),
                        config={"response_mime_type": "application/json"},
                    ),
                    timeout=GEMINI_TIMEOUT_SECONDS,
                )
                ai_raw = json.loads(response.text)
                summary, questions = parse_analysis(ai_raw)
            except Exception as exc:
                summary = f"AI analysis unavailable for this run: {exc}"
                questions = []
                ai_raw = {"error": str(exc)}

        return {
            "date": target.iso_date,
            "community": community,
            "totals": {"messages": total_msg_count, "users": len(user_counts)},
            "active_hours_sgt": hour_counts,
            "analysis": {"summary": summary, "questions": questions},
            "sections": [{"name": name, "msgs": count} for name, count in section_counts.most_common()],
            "leaderboards": {
                "community_users": [
                    {"name": name, "count": count}
                    for name, count in user_counts.most_common()
                    if name not in MOD_MAPPING.values()
                ][:5],
                "moderators": [
                    {"name": name, "count": count}
                    for name, count in user_counts.most_common()
                    if name in MOD_MAPPING.values()
                ],
            },
            "raw_ai_analysis": ai_raw,
            "metadata": {
                "target_date": target.label_short,
                "timezone": "Asia/Singapore",
                "report_date": target.iso_date,
            },
        }


def persist_report(report: dict) -> None:
    supabase = get_supabase()
    report_date = report["metadata"]["report_date"]
    community = report["community"]
    source_run = upsert_source_run(
        supabase,
        source_type="telegram_daily",
        community=community,
        report_date=report_date,
        schedule_basis="asia_singapore",
        raw_payload=report,
    )
    row = {
        "source_run_id": source_run["id"],
        "community": community,
        "report_date": report_date,
        "total_messages": report["totals"]["messages"],
        "active_users": report["totals"]["users"],
        "summary": report["analysis"]["summary"],
        "questions": report["analysis"]["questions"],
        "active_hours_sgt": report["active_hours_sgt"],
        "sections": report["sections"],
        "community_users": report["leaderboards"]["community_users"],
        "moderators": report["leaderboards"]["moderators"],
        "raw_payload": report,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    upsert_table(supabase, "telegram_daily_reports", row, "community,report_date")


async def main() -> None:
    report = await build_report()
    persist_report(report)
    print(f"Saved Telegram daily report for {report['metadata']['report_date']} to Supabase.")


if __name__ == "__main__":
    asyncio.run(main())
