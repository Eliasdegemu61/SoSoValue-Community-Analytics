from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


SINGAPORE_TZ = ZoneInfo("Asia/Singapore")
UTC = timezone.utc


@dataclass(frozen=True)
class DateTarget:
    report_date: date
    label_short: str
    iso_date: str


def format_short_label(target_date: date, pad_day: bool = False) -> str:
    month = target_date.strftime("%b").lower()
    day = target_date.strftime("%d") if pad_day else str(target_date.day)
    return f"{month}{day}"


def singapore_yesterday() -> DateTarget:
    now_sg = datetime.now(SINGAPORE_TZ)
    target = (now_sg - timedelta(days=1)).date()
    return DateTarget(target, format_short_label(target), target.isoformat())


def utc_yesterday() -> DateTarget:
    now_utc = datetime.now(UTC)
    target = (now_utc - timedelta(days=1)).date()
    return DateTarget(target, format_short_label(target, pad_day=True), target.isoformat())


def singapore_day_bounds_utc(target_date: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(target_date, time.min, tzinfo=SINGAPORE_TZ)
    end_local = datetime.combine(target_date, time.max.replace(microsecond=0), tzinfo=SINGAPORE_TZ)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)

