from datetime import datetime, time, timedelta

from django.utils import timezone


RANGE_LABELS = {
    1: "Today",
    7: "Last 7 days",
    30: "Last 30 days",
    180: "Last 6 months",
    365: "Last 12 months",
}


def parse_days_param(raw_value, default=1, max_days=365):
    try:
        days = int(raw_value)
    except (TypeError, ValueError):
        return default

    if days < 1:
        return default

    return min(days, max_days)


def get_date_window(days):
    today = timezone.localdate()
    start_date = today - timedelta(days=days - 1)
    current_tz = timezone.get_current_timezone()
    start_datetime = timezone.make_aware(datetime.combine(start_date, time.min), current_tz)
    return today, start_date, start_datetime


def get_range_label(days):
    return RANGE_LABELS.get(days, f"Last {days} days")
