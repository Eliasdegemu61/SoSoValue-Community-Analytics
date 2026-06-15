# GitHub Actions Setup

This repo is ready to run the website and the daily Supabase pipelines from GitHub Actions.

## What runs automatically

There are two workflow files:

- `.github/workflows/singapore-pipeline.yml`
- `.github/workflows/x-pipeline.yml`

### Singapore pipeline

Runs at `16:03 UTC` every day.

That is `00:03` the next day in Singapore.

It runs:

1. `telegram_daily_supabase`
2. `discord_daily_supabase`
3. `weekly_report_supabase`
4. `weekly_suggestions_supabase`

The weekly jobs depend on the Discord job through workflow `needs`, so they do not run before Discord finishes.

### X pipeline

Runs at `00:05 UTC` every day.

It runs:

1. `x_daily_supabase`

## What data goes where

Every script writes directly to Supabase.

- `source_runs`
- `telegram_daily_reports`
- `discord_daily_reports`
- `x_daily_reports`
- `weekly_reports`
- `weekly_suggestions`

The website reads from Supabase through:

- `app/api/dashboard/route.ts`

## Required GitHub repository secrets

Open your GitHub repo:

`Settings -> Secrets and variables -> Actions -> New repository secret`

Create these secrets exactly with these names:

- `DISCORD_TOKEN`
- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELEGRAM_STRING_SESSION`
- `GEMINI_API_KEY`
- `XAI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_PUBLISHABLE_KEY`

## How to get TELEGRAM_STRING_SESSION

Run this locally one time:

```powershell
python -m backend_supabase.generate_telegram_string_session
```

It will ask for your Telegram login if needed and print a long string.

Copy that string into the GitHub secret:

- `TELEGRAM_STRING_SESSION`

Do not commit the session string into the repo.

## How to test the workflows manually

After you push the repo:

1. Open `Actions` in GitHub
2. Click `Singapore Pipeline`
3. Click `Run workflow`
4. Run `X Pipeline` separately too

This lets you verify everything before waiting for cron.

## Notes

- GitHub cron uses UTC.
- Supabase stores the historical rows by `report_date`, so the website calendar keeps working.
- `.env` is only for local development. Production secrets live in GitHub Actions secrets.
