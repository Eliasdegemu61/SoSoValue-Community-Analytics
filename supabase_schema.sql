create extension if not exists pgcrypto;

create table if not exists public.source_runs (
  id uuid primary key default gen_random_uuid(),
  source_type text not null check (source_type in (
    'telegram_daily',
    'discord_daily',
    'x_daily',
    'weekly_report',
    'weekly_suggestions'
  )),
  community text null check (community in ('SOSOVALUE', 'SODEX')),
  report_date date not null,
  schedule_basis text not null check (schedule_basis in ('asia_singapore', 'utc')),
  status text not null default 'completed' check (status in ('pending', 'running', 'completed', 'failed')),
  raw_payload jsonb not null default '{}'::jsonb,
  started_at timestamptz not null default now(),
  completed_at timestamptz null,
  error_message text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (source_type, community, report_date)
);

create table if not exists public.telegram_daily_reports (
  id uuid primary key default gen_random_uuid(),
  source_run_id uuid not null unique references public.source_runs(id) on delete cascade,
  community text not null check (community in ('SOSOVALUE', 'SODEX')),
  report_date date not null,
  total_messages integer not null default 0,
  active_users integer not null default 0,
  summary text null,
  questions jsonb not null default '[]'::jsonb,
  active_hours_sgt jsonb not null default '{}'::jsonb,
  sections jsonb not null default '[]'::jsonb,
  community_users jsonb not null default '[]'::jsonb,
  moderators jsonb not null default '[]'::jsonb,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (community, report_date)
);

create table if not exists public.discord_daily_reports (
  id uuid primary key default gen_random_uuid(),
  source_run_id uuid not null unique references public.source_runs(id) on delete cascade,
  report_date date not null unique,
  total_messages integer not null default 0,
  active_users integer not null default 0,
  hourly_activity jsonb not null default '{}'::jsonb,
  reports jsonb not null default '{}'::jsonb,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.x_daily_reports (
  id uuid primary key default gen_random_uuid(),
  source_run_id uuid not null unique references public.source_runs(id) on delete cascade,
  report_date date not null unique,
  summary jsonb not null default '{}'::jsonb,
  top_questions jsonb not null default '{}'::jsonb,
  top_engaged_posts jsonb not null default '[]'::jsonb,
  captured_at text null,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.weekly_reports (
  id uuid primary key default gen_random_uuid(),
  source_run_id uuid not null unique references public.source_runs(id) on delete cascade,
  report_date date not null unique,
  reports jsonb not null default '{}'::jsonb,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.weekly_suggestions (
  id uuid primary key default gen_random_uuid(),
  source_run_id uuid not null unique references public.source_runs(id) on delete cascade,
  report_date date not null unique,
  team_suggestions jsonb not null default '[]'::jsonb,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_source_runs_report_date on public.source_runs(report_date desc);
create index if not exists idx_source_runs_source_type on public.source_runs(source_type);
create index if not exists idx_telegram_daily_reports_lookup on public.telegram_daily_reports(community, report_date desc);
create index if not exists idx_discord_daily_reports_lookup on public.discord_daily_reports(report_date desc);
create index if not exists idx_x_daily_reports_lookup on public.x_daily_reports(report_date desc);
create index if not exists idx_weekly_reports_lookup on public.weekly_reports(report_date desc);
create index if not exists idx_weekly_suggestions_lookup on public.weekly_suggestions(report_date desc);

alter table public.source_runs enable row level security;
alter table public.telegram_daily_reports enable row level security;
alter table public.discord_daily_reports enable row level security;
alter table public.x_daily_reports enable row level security;
alter table public.weekly_reports enable row level security;
alter table public.weekly_suggestions enable row level security;

drop policy if exists "public read telegram_daily_reports" on public.telegram_daily_reports;
create policy "public read telegram_daily_reports"
on public.telegram_daily_reports
for select
to anon, authenticated
using (true);

drop policy if exists "public read discord_daily_reports" on public.discord_daily_reports;
create policy "public read discord_daily_reports"
on public.discord_daily_reports
for select
to anon, authenticated
using (true);

drop policy if exists "public read x_daily_reports" on public.x_daily_reports;
create policy "public read x_daily_reports"
on public.x_daily_reports
for select
to anon, authenticated
using (true);

drop policy if exists "public read weekly_reports" on public.weekly_reports;
create policy "public read weekly_reports"
on public.weekly_reports
for select
to anon, authenticated
using (true);

drop policy if exists "public read weekly_suggestions" on public.weekly_suggestions;
create policy "public read weekly_suggestions"
on public.weekly_suggestions
for select
to anon, authenticated
using (true);
