# accounts/authentication.py
import logging
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.middleware import get_user
from django.http import JsonResponse
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware

logger = logging.getLogger(__name__)

class JWTAuthenticationFromCookies(JWTAuthentication):
    def authenticate(self, request):
        access_token = request.COOKIES.get('access_token')
        if not access_token:
            return None

        validated_token = self.get_validated_token(access_token)
        user = self.get_user(validated_token)

        if not user or not user.is_active:
            raise AuthenticationFailed(_('User is inactive or deleted.'))

        return (user, validated_token)


def _parse_cookies_from_headers(scope):
    """Parse cookies directly from raw WebSocket scope headers."""
    headers = dict(scope.get('headers', []))
    cookie_header = headers.get(b'cookie', b'')
    if isinstance(cookie_header, bytes):
        cookie_header = cookie_header.decode('latin-1')
    cookies = {}
    for part in cookie_header.split(';'):
        part = part.strip()
        if '=' in part:
            key, _, value = part.partition('=')
            cookies[key.strip()] = value.strip()
    return cookies


@database_sync_to_async
def get_user_from_jwt_cookie(scope):
    # Prefer CookieMiddleware-parsed cookies; fall back to parsing headers directly.
    cookies = scope.get('cookies') or _parse_cookies_from_headers(scope)
    access_token = cookies.get('access_token')
    if not access_token:
        logger.debug('[WS Auth] No access_token cookie found in WebSocket scope')
        return AnonymousUser()
    try:
        auth = JWTAuthentication()
        validated_token = auth.get_validated_token(access_token)
        user = auth.get_user(validated_token)
        if user and user.is_active:
            logger.debug('[WS Auth] Authenticated WebSocket user: %s', user.username)
            return user
        return AnonymousUser()
    except Exception as e:
        logger.warning('[WS Auth] JWT validation failed for WebSocket: %s', e)
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        if scope['type'] == 'websocket':
            scope['user'] = await get_user_from_jwt_cookie(scope)
        await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    from channels.sessions import CookieMiddleware
    return CookieMiddleware(JWTAuthMiddleware(inner))