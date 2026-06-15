# Supabase backend scripts

These are new Supabase-native replacements for the old Pydroid scripts.

They are designed to be tested from this repo first, then moved to your production backend environment.

## Scripts

- `discord_daily_supabase.py`
- `telegram_daily_supabase.py`
- `weekly_report_supabase.py`
- `weekly_suggestions_supabase.py`
- `x_daily_supabase.py`

## Expected env vars

- `DISCORD_TOKEN`
- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `GEMINI_API_KEY`
- `XAI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`

## Scheduling intent

- Discord daily: previous day in `Asia/Singapore`
- Telegram daily: previous day in `Asia/Singapore`
- Weekly report: after Discord daily
- Weekly suggestions: after weekly report
- X daily: previous day in `UTC`

## Local test

Install requirements:

```powershell
python -m pip install -r backend_supabase/requirements.txt
```

Run one script:

```powershell
python -m backend_supabase.discord_daily_supabase
```
