"""
Celery tasks for analytics.

Replaces the previous fire-and-forget threading.Thread pattern. Worker
concurrency caps the number of simultaneous Postgres connections used by
analytics — that is what stops the "too many clients" saturation.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.db import close_old_connections
from django.utils import timezone


logger = logging.getLogger(__name__)


@shared_task(
    name="analytics.tasks.record_visit_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
)
def record_visit_task(payload: dict) -> None:
    """
    Worker-side persistence of a single visit.

    `payload` is a plain dict (must be JSON-serializable) built by the
    middleware. We never pass the live `request` across the queue.
    """
    from .services import record_visit  # local import keeps celery boot light

    try:
        attribution = dict(payload.get("attribution") or {})
        # Carry user_id and request metadata across the queue boundary.
        if payload.get("user_id") is not None:
            attribution.setdefault("user_id", payload["user_id"])

        record_visit(
            path=payload.get("path") or "",
            attribution_payload=attribution,
            request=None,
            referrer=payload.get("referrer"),
            user=None,
            visitor_id=payload.get("visitor_id"),
            is_bot=bool(payload.get("is_bot")),
        )
    finally:
        close_old_connections()


@shared_task(name="analytics.tasks.prune_stale_presence")
def prune_stale_presence() -> None:
    """
    Drop presence entries older than 5 minutes from the cached dict.
    Cheap, runs every minute. No DB access.
    """
    from django.core.cache import cache
    from .services import ONLINE_SET_KEY

    presence = cache.get(ONLINE_SET_KEY, {}) or {}
    if not isinstance(presence, dict) or not presence:
        return

    cutoff = (timezone.now() - timedelta(minutes=5)).timestamp()
    cleaned = {k: v for k, v in presence.items() if v.get("last_active", 0) > cutoff}

    if len(cleaned) != len(presence):
        cache.set(ONLINE_SET_KEY, cleaned, timeout=3600)


@shared_task(name="analytics.tasks.snapshot_daily_counters")
def snapshot_daily_counters() -> None:
    """
    Once per day, log the Redis-tracked counters so we can keep them around
    even after the 8-day Redis retention expires. Reads Redis, writes nothing
    by default — extend to write a DailySnapshot row when needed.
    """
    from .redis_tracking import get_today_summary

    yesterday = (timezone.now() - timedelta(days=1)).date()
    summary = get_today_summary(on=yesterday)
    logger.info("[analytics] daily snapshot %s -> %s", yesterday.isoformat(), summary)
    close_old_connections()
