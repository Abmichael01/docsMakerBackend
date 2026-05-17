import uuid

from .utils import is_bot_user_agent
from .services import update_presence
from .redis_tracking import incr_visit_counter, mark_seen
from .tasks import record_visit_task


def resolve_request_user(request):
    """
    Returns the authenticated user for the request, supporting both
    Django session auth (request.user) and DRF Token auth (Authorization header).
    Token resolution is needed because this middleware runs before DRF's
    authentication layer, so request.user is anonymous for token requests.
    """
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        return user

    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header:
        return None

    parts = auth_header.split()
    if len(parts) != 2:
        return None

    scheme, token_key = parts
    if scheme.lower() not in ('token', 'bearer'):
        return None

    try:
        from rest_framework.authtoken.models import Token
        token = Token.objects.select_related('user').get(key=token_key)
        return token.user
    except Exception:
        return None


_VISIT_LOG_SKIP_PREFIXES = (
    '/static/',
    '/media/',
    '/admin/',
    '/__debug__/',
    '/favicon.ico',
    '/api/u/p/',
    '/api/analytics/',
    '/api/auth/',
    '/api/token/',
    '/_next/',
)


def _should_record_visit(path):
    if not path:
        return False
    return not any(path.startswith(p) for p in _VISIT_LOG_SKIP_PREFIXES)


def _build_attribution_payload(request):
    """Snapshot just the bits of the request the worker needs (JSON-safe)."""
    return {
        "referrer": request.META.get('HTTP_REFERER'),
        "user_agent": request.META.get('HTTP_USER_AGENT', '')[:1000],
        "ip": request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
              or request.META.get('REMOTE_ADDR'),
        "query": request.META.get('QUERY_STRING', '')[:500],
    }


class VisitorTrackingMiddleware:
    """
    Redis-first request tracking.

    Hot path per request:
        - assign/persist a visitor cookie
        - update presence (Redis only)
        - increment a daily counter (Redis only)
        - on FIRST sighting of this identity today, enqueue ONE Celery task
          that writes a VisitorLog row in a worker process

    No threads spawned. No Postgres connection opened from the request thread.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        vuid = request.COOKIES.get('vux_id')
        new_vuid_created = False
        if not vuid:
            vuid = str(uuid.uuid4())
            new_vuid_created = True

        request.vuid = vuid
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        request.is_bot = is_bot_user_agent(user_agent)

        if not request.is_bot and _should_record_visit(request.path):
            resolved_user = resolve_request_user(request)
            request.resolved_user = resolved_user
            user_id = getattr(resolved_user, 'id', None) if resolved_user else None
            is_auth = bool(user_id)

            # 1. Realtime presence (Redis only).
            update_presence(vuid, user=resolved_user)

            # 2. Daily counters (Redis only — cheap, never touches DB).
            incr_visit_counter(authenticated=is_auth)

            # 3. Only persist a VisitorLog row the FIRST time we see this
            #    identity today. Everything after that is free.
            if mark_seen(vuid, user_id=user_id):
                record_visit_task.delay({
                    "path": request.path,
                    "visitor_id": vuid,
                    "user_id": user_id,
                    "is_bot": False,
                    "attribution": _build_attribution_payload(request),
                    "referrer": request.META.get('HTTP_REFERER'),
                })

        response = self.get_response(request)

        if new_vuid_created:
            response.set_cookie(
                'vux_id',
                vuid,
                max_age=365 * 24 * 60 * 60,
                httponly=True,
                samesite='Lax',
            )

        return response
