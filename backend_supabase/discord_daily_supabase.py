from __future__ import annotations

import asyncio
import collections
import json
from datetime import datetime, timezone

import discord
from google import genai

from .config import load_env, require_env
from .date_utils import singapore_day_bounds_utc, singapore_yesterday
from .supabase_store import get_supabase, upsert_source_run, upsert_table


load_env()

DISCORD_TOKEN = require_env("DISCORD_TOKEN")
GEMINI_API_KEY = require_env("GEMINI_API_KEY")

MODERATOR_IDS = [1035494175606591499, 952765858822881310, 927577910892711946]
CHANNELS = {
    "announcements": 1010022505148330014,
    "general": 1407607762392973393,
    "gm": 1407607432892514406,
    "research-submissions": 1444176835054276762,
    "help-general": 1407628434007523348,
    "feedback": 1435653916174979233,
}

MAX_MESSAGES_PER_CHANNEL = 5000
GEMINI_TIMEOUT_SECONDS = 90


async def build_report() -> dict:
    target = singapore_yesterday()
    start_utc, end_utc = singapore_day_bounds_utc(target.report_date)
    tz_target = timezone.utc

    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    bot = discord.Client(intents=discord.Intents.all())
    done_event = asyncio.Event()
    result_holder: dict[str, dict] = {}

    @bot.event
    async def on_ready() -> None:
        print(f"Connected as {bot.user}. Starting Discord extraction...")
        stats = {
            "metadata": {
                "target_date": target.label_short,
                "timezone": "Asia/Singapore",
                "report_date": target.iso_date,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            },
            "vitals": {"total_messages": 0, "active_users": 0, "gm_count": 0},
            "hourly_activity": {datetime(2000, 1, 1, h).strftime("%I %p"): 0 for h in range(24)},
            "top_moderators": [],
            "top_chatters": [],
            "reports": {
                "retail": {"summary": "", "questions": []},
                "trading": {"summary": "", "questions": []},
                "tickets": {"summary": "", "questions": []},
                "dev": {"summary": "", "questions": []},
            },
        }

        active_user_ids = set()
        mod_counts = collections.defaultdict(int)
        user_counts = collections.defaultdict(int)
        chat_corpus = []

        for name, channel_id in CHANNELS.items():
            print(f"Fetching channel: {name} ({channel_id})")
            channel = bot.get_channel(channel_id)
            if not channel:
                print(f"Channel not found: {name}")
                continue
            channel_count = 0
            async for msg in channel.history(limit=MAX_MESSAGES_PER_CHANNEL, after=start_utc, before=end_utc):
                if msg.author.bot:
                    continue
                stats["vitals"]["total_messages"] += 1
                channel_count += 1
                active_user_ids.add(msg.author.id)
                msg_sg = msg.created_at.astimezone(start_utc.tzinfo or tz_target)
                hour_label = msg_sg.strftime("%I %p")
                stats["hourly_activity"][hour_label] += 1
                user_counts[msg.author.name] += 1
                if "gm" in msg.content.lower().split():
                    stats["vitals"]["gm_count"] += 1
                if msg.author.id in MODERATOR_IDS:
                    mod_counts[msg.author.name] += 1
                if name in {"general", "help-general", "feedback"}:
                    chat_corpus.append(f"{msg.author.name}: {msg.content}")
                if channel_count % 500 == 0:
                    print(f"  {name}: processed {channel_count} messages")

            print(f"Finished channel {name}: {channel_count} messages")

        stats["vitals"]["active_users"] = len(active_user_ids)
        stats["top_moderators"] = [
            {"name": name, "count": count}
            for name, count in sorted(mod_counts.items(), key=lambda item: item[1], reverse=True)
        ]
        stats["top_chatters"] = [
            {"name": name, "count": count}
            for name, count in sorted(user_counts.items(), key=lambda item: item[1], reverse=True)[:10]
        ]

        if chat_corpus:
            print(f"Sending {len(chat_corpus[-1500:])} Discord messages to Gemini...")
            prompt = (
                "Analyze these Discord logs and return JSON with a 'reports' object. "
                "The object must contain retail, trading, tickets, and dev. "
                "Each section must have 'summary' and 'questions'."
            )
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        gemini_client.models.generate_content,
                        model="gemini-3-flash-preview",
                        contents=f"{prompt}\n\nDATA:\n" + "\n".join(chat_corpus[-1500:]),
                        config={"response_mime_type": "application/json"},
                    ),
                    timeout=GEMINI_TIMEOUT_SECONDS,
                )
                ai_data = json.loads(response.text)
                if "reports" in ai_data:
                    stats["reports"] = ai_data["reports"]
                print("Gemini analysis completed.")
            except Exception as exc:
                print(f"Gemini analysis failed or timed out: {exc}")

        result_holder["stats"] = stats
        print(f"Discord extraction complete for {target.iso_date}.")
        done_event.set()
        await bot.close()

    async with bot:
        await bot.start(DISCORD_TOKEN)
    await done_event.wait()
    return result_holder["stats"]


def persist_report(report: dict) -> None:
    supabase = get_supabase()
    report_date = report["metadata"]["report_date"]
    source_run = upsert_source_run(
        supabase,
        source_type="discord_daily",
        community=None,
        report_date=report_date,
        schedule_basis="asia_singapore",
        raw_payload=report,
    )
    row = {
        "source_run_id": source_run["id"],
        "report_date": report_date,
        "total_messages": report["vitals"]["total_messages"],
        "active_users": report["vitals"]["active_users"],
        "hourly_activity": report["hourly_activity"],
        "reports": report["reports"],
        "raw_payload": report,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    upsert_table(supabase, "discord_daily_reports", row, "report_date")


async def main() -> None:
    report = await build_report()
    persist_report(report)
    print(f"Saved Discord daily report for {report['metadata']['report_date']} to Supabase.")


if __name__ == "__main__":
    asyncio.run(main())
