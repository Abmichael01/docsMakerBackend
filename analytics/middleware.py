import uuid
from .utils import is_bot_user_agent
from .services import record_visit, update_presence
import threading
import hashlib
from django.utils import timezone
from django.core.cache import cache


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


# Paths that should NOT contribute to visitor logs (avoid noise / recursion).
_VISIT_LOG_SKIP_PREFIXES = (
    '/static/',
    '/media/',
    '/admin/',
    '/__debug__/',
    '/favicon.ico',
    '/api/u/p/',
    '/api/analytics/',             # All analytics endpoints
    '/api/auth/',                  # Auth is too noisy
    '/api/token/',
    '/_next/',                     # Next.js internal calls
)


def _should_record_visit(path):
    if not path:
        return False
    return not any(path.startswith(p) for p in _VISIT_LOG_SKIP_PREFIXES)


class VisitorTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Identity Management (Standardized Persistent VUID)
        vuid = request.COOKIES.get('vux_id')
        new_vuid_created = False
        if not vuid:
            vuid = str(uuid.uuid4())
            new_vuid_created = True

        request.vuid = vuid
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        request.is_bot = is_bot_user_agent(user_agent)

        if not request.is_bot:
            # 2. Resolve user once (handles both session + DRF token auth).
            #    DRF token auth runs at the view layer, so request.user is
            #    AnonymousUser here for API calls — we look up the token directly.
            resolved_user = resolve_request_user(request)
            request.resolved_user = resolved_user

            # 3. Active User Tracking (Presence) — every request keeps the
            #    "online now" list accurate. Identified users are grouped by
            #    username so multiple tabs/devices count as one person.
            update_presence(vuid, user=resolved_user)

            # 4. Server-side Visit Tracking — primary source of truth.
            #    Frontend tracking is unreliable (ad blockers strip /analytics/
            #    URLs), so we record visits server-side for any meaningful
            #    request path. record_visit() dedups within 15 minutes per
            #    (visitor, path) so this isn't write-amplified.
            if _should_record_visit(request.path):
                # Patch request.user so record_visit() picks up the resolved user
                # (record_visit reads request.user via get_attribution_for_request).
                if resolved_user is not None and not getattr(getattr(request, 'user', None), 'is_authenticated', False):
                    request.user = resolved_user
                
                # Senior Optimization: Fast Deduplication Check (Redis)
                # Check here BEFORE spawning a thread to save CPU/RAM/Threads.
                # If they hit the same page today, we skip.
                today = timezone.now().date().isoformat()
                path_hash = hashlib.md5(request.path.encode()).hexdigest()[:10]
                dedup_key = f"vlog:dedup:vlog:{vuid}:{path_hash}:{today}"
                
                if not cache.get(dedup_key):
                    # Senior Optimization: Fire-and-Forget background thread.
                    # This ensures the user gets their response IMMEDIATELY
                    # without waiting for the Database write.
                    threading.Thread(
                        target=record_visit,
                        kwargs={
                            "path": request.path,
                            "request": request,
                            "visitor_id": vuid,
                        },
                        daemon=True
                    ).start()

        response = self.get_response(request)

        # 5. Persist the identity cookie for 1 year
        if new_vuid_created:
            response.set_cookie(
                'vux_id',
                vuid,
                max_age=365 * 24 * 60 * 60,
                httponly=True,
                samesite='Lax',
            )

        return response

