"""
Redis-first tracking primitives.

Goal: answer the only questions we actually care about, without hitting Postgres
on every request:

    1. Did this user/visitor come today?     -> SISMEMBER seen:{date}
    2. How many visits (anon vs auth)?       -> GET count:{date}:{kind}
    3. Did a registered user come today?     -> SISMEMBER seen:users:{date}
    4. Who is currently online?              -> handled by analytics.services.presence

Keys auto-expire after RETENTION_DAYS so the Redis footprint stays bounded.
A nightly Celery beat job snapshots daily totals to Postgres if we ever want
to look further back than RETENTION_DAYS.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from django.core.cache import cache
from django.utils import timezone


RETENTION_SECONDS = 60 * 60 * 24 * 8  # 8 days of hot data in Redis


def _today_iso() -> str:
    return timezone.now().date().isoformat()


def _client():
    """Return the raw Redis client from django-redis, or None if unavailable."""
    try:
        from django_redis import get_redis_connection
        return get_redis_connection("default")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------

def mark_seen(visitor_id: str, user_id: Optional[int] = None) -> bool:
    """
    Record that a visitor (and optionally an authenticated user) was seen today.

    Returns True if this is the FIRST sighting today for this identity — the
    caller uses this signal to decide whether to enqueue a Postgres write.
    """
    if not visitor_id and not user_id:
        return False

    client = _client()
    today = _today_iso()
    is_first = False

    if client is not None:
        pipe = client.pipeline()
        if visitor_id:
            pipe.sadd(f"seen:visitors:{today}", visitor_id)
            pipe.expire(f"seen:visitors:{today}", RETENTION_SECONDS)
        if user_id:
            pipe.sadd(f"seen:users:{today}", user_id)
            pipe.expire(f"seen:users:{today}", RETENTION_SECONDS)
        results = pipe.execute()
        # SADD returns 1 if the element was newly added
        is_first = any(r == 1 for r in results[::2])
    else:
        # Cache fallback — coarse, not perfect, but safe under outage
        key = f"seen:fallback:{today}:{user_id or visitor_id}"
        if cache.get(key):
            is_first = False
        else:
            cache.set(key, 1, timeout=RETENTION_SECONDS)
            is_first = True

    return is_first


def incr_visit_counter(authenticated: bool) -> None:
    """Bump the daily visit counter — anon or auth."""
    client = _client()
    today = _today_iso()
    kind = "auth" if authenticated else "anon"
    key = f"count:visits:{today}:{kind}"

    if client is not None:
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, RETENTION_SECONDS)
        pipe.execute()
    else:
        # locmem fallback
        current = cache.get(key, 0)
        cache.set(key, current + 1, timeout=RETENTION_SECONDS)


# ---------------------------------------------------------------------------
# Read path (used by admin dashboard for live "today" numbers)
# ---------------------------------------------------------------------------

def get_today_summary(on: Optional[date] = None) -> dict:
    """Return {visits_anon, visits_auth, unique_visitors, unique_users}."""
    day = (on or timezone.now().date()).isoformat()
    client = _client()

    if client is not None:
        pipe = client.pipeline()
        pipe.get(f"count:visits:{day}:anon")
        pipe.get(f"count:visits:{day}:auth")
        pipe.scard(f"seen:visitors:{day}")
        pipe.scard(f"seen:users:{day}")
        anon, auth, uniq_v, uniq_u = pipe.execute()
        return {
            "visits_anon": int(anon or 0),
            "visits_auth": int(auth or 0),
            "unique_visitors": int(uniq_v or 0),
            "unique_users": int(uniq_u or 0),
        }

    return {
        "visits_anon": int(cache.get(f"count:visits:{day}:anon", 0) or 0),
        "visits_auth": int(cache.get(f"count:visits:{day}:auth", 0) or 0),
        "unique_visitors": 0,
        "unique_users": 0,
    }


def is_user_seen_today(user_id: int) -> bool:
    client = _client()
    if client is None or not user_id:
        return False
    return bool(client.sismember(f"seen:users:{_today_iso()}", user_id))
