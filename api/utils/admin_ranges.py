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


def get_admin_date_range(days_param=None, date_str=None):
    """
    Unified utility to get date range for admin views.
    Returns: (start_datetime, end_datetime, range_label, days_count)
    """
    current_tz = timezone.get_current_timezone()
    
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            start_datetime = timezone.make_aware(datetime.combine(selected_date, time.min), current_tz)
            end_datetime = timezone.make_aware(datetime.combine(selected_date, time.max), current_tz)
            return start_datetime, end_datetime, selected_date.strftime('%b %d, %Y'), 1
        except (ValueError, TypeError):
            pass

    days = parse_days_param(days_param, default=1)
    today = timezone.localdate()
    start_date = today - timedelta(days=days - 1)
    start_datetime = timezone.make_aware(datetime.combine(start_date, time.min), current_tz)
    end_datetime = timezone.now()
    return start_datetime, end_datetime, get_range_label(days), days


def get_range_label(days):
    return RANGE_LABELS.get(days, f"Last {days} days")
