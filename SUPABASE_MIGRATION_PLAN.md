# Supabase Migration Plan

## Supabase project setup

Create one Supabase project for production first.

Recommended names:

- Supabase organization: your existing org
- Supabase project name: `sosovalue-community-prod`
- Database password: generate and save it in your password manager
- Region: the closest stable region to your users and automation

Recommended local naming:

- frontend repo: `sosovalue-community-analytics`
- backend collectors folder: `sosovalue-community-backend`
- Supabase schema name: keep `public`

Recommended app-level naming:

- website app: `community_dashboard`
- pipeline name: `community_ingestion`

## Secrets to prepare

These should not stay hardcoded in Python anymore.

- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_PUBLISHABLE_KEY`
- `DISCORD_TOKEN`
- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `GEMINI_API_KEY`
- `XAI_API_KEY`

Optional during migration only:

- `GITHUB_TOKEN`

## Scheduling rules

These are the production rules we are designing for.

- Discord daily:
  target date = previous day in `Asia/Singapore`
- Telegram daily:
  target date = previous day in `Asia/Singapore`
- X daily:
  target date = previous day in `UTC`
- Weekly report:
  run after Discord daily is available, using a 7-day window ending on the Discord target date
- Weekly suggestions:
  run after the weekly report is available

Suggested schedule:

- `00:02` Singapore time: Telegram daily
- `00:03` Singapore time: Discord daily
- `00:08` Singapore time: Weekly report
- `00:10` Singapore time: Weekly suggestions
- `00:05` UTC: X daily

Important:

- Weekly jobs should not rely only on time delay.
- They should also verify that the needed Discord daily row already exists in Supabase.

## Current website data sources

The frontend currently reads raw JSON directly from GitHub in [`app/page.tsx`](</c:/Users/elias/Desktop/sosovalue community v3/sosovalue-community-analytics/app/page.tsx:96>).

Daily file patterns:

- Telegram SoSoValue: `Json-data/SOSOVALUE/{mon}{day}_processed.json`
- Telegram SoDex: `Json-data/SODEX/{mon}{day}_processed.json`
- Discord daily: `discord-bot-data/{mon}{day}data.json`
- X daily: `soso-x-analysis/{mon}{day}.json`
- Weekly report: `discord-bot-data/weekly{mon}{day}.json`
- Weekly suggestions: `discord-bot-data/weekly_suggestions/segg{mon}{day}.json`

Example files confirmed for June 14, 2026:

- Telegram SoSoValue: `SOSOVALUE/jun14_processed.json`
- Telegram SoDex: missing on GitHub for `jun14`
- Discord daily: `jun14data.json`
- X daily: `jun14.json`
- Weekly report: `weeklyjun14.json`
- Weekly suggestions: `weekly_suggestions/seggjun14.json`

## Current payload shapes

### 1. Telegram daily

Produced by [`sosovalue.py`](</c:/Users/elias/Desktop/sosovalue community backend codes/sosovalue.py:1>) and consumed in [`app/page.tsx`](</c:/Users/elias/Desktop/sosovalue community v3/sosovalue-community-analytics/app/page.tsx:589>).

```json
{
  "date": "2026-06-14",
  "totals": { "messages": 431, "users": 148 },
  "active_hours_sgt": { "12 AM": 28, "...": 20 },
  "ai_analysis": "Summary: ...\n\nTop Community Questions:\n1. ...",
  "sections": [{ "name": "General", "msgs": 286 }],
  "leaderboards": {
    "community_users": [{ "name": "user", "count": 16 }],
    "moderators": [{ "name": "mod", "count": 39 }]
  }
}
```

Notes:

- `ai_analysis` is a single formatted string, not structured JSON.
- The UI parses that string into summary and questions.
- The TypeScript interface still says `points`, but the live JSON uses `count`.

### 2. Discord daily

Produced by [`discord55.py`](</c:/Users/elias/Desktop/sosovalue community backend codes/discord55.py:1>) and consumed in [`app/page.tsx`](</c:/Users/elias/Desktop/sosovalue community v3/sosovalue-community-analytics/app/page.tsx:520>).

```json
{
  "vitals": {
    "total_messages": 1128,
    "active_users": 243
  },
  "hourly_activity": { "12 AM": 105, "...": 49 },
  "reports": {
    "retail": { "summary": "...", "questions": ["...", "..."] },
    "trading": { "summary": "...", "questions": ["...", "..."] },
    "tickets": { "summary": "...", "questions": ["...", "..."] },
    "dev": { "summary": "...", "questions": ["...", "..."] }
  }
}
```

Notes:

- The script currently writes `active_users_count`, but the website reads `active_users`.
- The live GitHub file uses `active_users`, so there is already some drift between script and repo output.

### 3. X / Twitter daily

Produced by [`xnew.py`](</c:/Users/elias/Desktop/sosovalue community backend codes/xnew.py:1>) and consumed in [`app/page.tsx`](</c:/Users/elias/Desktop/sosovalue community v3/sosovalue-community-analytics/app/page.tsx:700>).

```json
{
  "summary": {
    "sosovalue": "...",
    "sodex": "...",
    "ssi": "..."
  },
  "top_questions": {
    "sosovalue": ["..."],
    "sodex": ["..."],
    "ssi": ["..."]
  },
  "Top poster username, post content, engagement, post link on that date with the highest engagement, atleast 3 posts": [
    {
      "username": "OjTheLight",
      "post_content": "...",
      "engagement": "Likes=86, Reposts=7, Quotes=0, Replies=33, Bookmarks=1, Views=6088",
      "post_link": "https://x.com/...",
      "date": "2026-06-14"
    }
  ],
  "timestamp": "2026-06-15 11:25:21"
}
```

Notes:

- The posts key is unstable and human-written.
- The UI already compensates by scanning keys that look like "top engaged posts".
- This source should be normalized before moving to Supabase.

### 4. Weekly report

Produced by [`Weeklyreport.py`](</c:/Users/elias/Desktop/sosovalue community backend codes/Weeklyreport.py:1>) and consumed in [`app/page.tsx`](</c:/Users/elias/Desktop/sosovalue community v3/sosovalue-community-analytics/app/page.tsx:986>).

```json
{
  "reports": {
    "retail": { "summary": "...", "questions": ["..."] },
    "trading": { "summary": "...", "questions": ["..."] },
    "tickets": { "summary": "...", "questions": ["..."] },
    "dev": { "summary": "...", "questions": ["..."] }
  }
}
```

### 5. Weekly team suggestions

Produced by [`suggestions22.py`](</c:/Users/elias/Desktop/sosovalue community backend codes/suggestions22.py:1>) and consumed in [`app/page.tsx`](</c:/Users/elias/Desktop/sosovalue community v3/sosovalue-community-analytics/app/page.tsx:919>).

```json
{
  "team_suggestions": [
    {
      "category": "dev",
      "action_point": "Fix ...",
      "action_type": "resolve"
    }
  ]
}
```

## Recommended Supabase model

Use normalized tables plus a raw JSON snapshot table.

### Core tables

`source_runs`

- `id uuid primary key`
- `source_type text`  
  `telegram_daily | discord_daily | x_daily | weekly_report | weekly_suggestions`
- `community text null`  
  `SOSOVALUE | SODEX | null`
- `report_date date not null`
- `status text not null`
- `raw_payload jsonb not null`
- `created_at timestamptz default now()`

`daily_metrics`

- `id uuid primary key`
- `source_run_id uuid references source_runs(id)`
- `source_type text not null`
- `community text null`
- `report_date date not null`
- `total_messages integer null`
- `active_users integer null`
- `gm_count integer null`
- `summary text null`

`hourly_activity`

- `id uuid primary key`
- `source_run_id uuid references source_runs(id)`
- `hour_label text not null`
- `message_count integer not null`

`report_sections`

- `id uuid primary key`
- `source_run_id uuid references source_runs(id)`
- `section_type text not null`
- `section_name text not null`
- `summary text null`

`report_questions`

- `id uuid primary key`
- `section_id uuid references report_sections(id)`
- `question_order integer not null`
- `question_text text not null`

`leaderboard_entries`

- `id uuid primary key`
- `source_run_id uuid references source_runs(id)`
- `board_type text not null`  
  `community_users | moderators | top_chatters | top_moderators`
- `display_name text not null`
- `value integer not null`
- `rank integer null`

`x_posts`

- `id uuid primary key`
- `source_run_id uuid references source_runs(id)`
- `topic text not null`  
  `sosovalue | sodex | ssi`
- `username text null`
- `content text null`
- `post_url text null`
- `likes integer null`
- `reposts integer null`
- `quotes integer null`
- `replies integer null`
- `views integer null`
- `raw_engagement text null`

`team_suggestions`

- `id uuid primary key`
- `source_run_id uuid references source_runs(id)`
- `category text not null`
- `action_point text not null`
- `action_type text not null`

## Best migration path

1. Keep your Python collectors, but stop writing to GitHub.
2. Add one shared Supabase helper module for inserts and updates.
3. Save raw JSON to `source_runs.raw_payload` first.
4. Normalize each payload into the other tables after insert.
5. Update the Next.js frontend to read from Supabase instead of raw GitHub files.
6. Run the collectors on a schedule:
   daily for Telegram, Discord, and X
   daily or weekly for the 7-day report and suggestions

## Automation recommendation

For full autonomy, the cleanest setup is:

- Supabase Postgres for storage
- Supabase Edge Functions or a small cron worker for scheduled runs
- GitHub Actions only if you want a low-cost first step
- Secrets stored in Supabase or GitHub Actions secrets, not inside the scripts

## Biggest cleanup items before migration

- Remove interactive `input()` from all five scripts.
- Replace hardcoded date parsing with automatic target-date selection.
- Standardize field names:
  `active_users` vs `active_users_count`
  `count` vs `points`
- Convert Telegram `ai_analysis` from one big string into structured fields:
  `summary`
  `questions[]`
- Rename the X posts field to a stable key like `top_engaged_posts`.
