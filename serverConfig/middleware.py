"""
Server-level middleware.

- `MediaCorsMiddleware`: dev-only CORS shim for /media/.
- `TrustedProxyMiddleware`: rewrites REMOTE_ADDR from X-Forwarded-For when
  we sit behind a known number of proxies (Cloudflare, load balancer).
  Without this, every request looks like it comes from the proxy and our
  rate limits / lockouts target the wrong IP.
"""
from django.conf import settings


class MediaCorsMiddleware:
    """CORS headers for /media/ in development only."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith('/media/'):
            response["Access-Control-Allow-Origin"] = "*"
            response["Cross-Origin-Resource-Policy"] = "cross-origin"
            response["Cross-Origin-Embedder-Policy"] = "credentialless"
        return response


class TrustedProxyMiddleware:
    """
    Resolve the real client IP when running behind one or more trusted proxies.

    Reads the number of trusted proxy hops from settings.TRUSTED_PROXY_HOPS
    (default 1 in production, 0 in dev). Picks the Nth-from-rightmost value in
    X-Forwarded-For and rewrites REMOTE_ADDR with it.

    Why Nth-from-right? Each proxy APPENDS the IP it saw to X-Forwarded-For,
    so the rightmost entries are the proxies you control, and the leftmost
    entry is what the client *claimed* (which can be spoofed). Trusting only
    as many hops as you actually have is the safe rule.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.hops = int(getattr(settings, 'TRUSTED_PROXY_HOPS', 0) or 0)

    def __call__(self, request):
        if self.hops > 0:
            xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
            if xff:
                parts = [p.strip() for p in xff.split(',') if p.strip()]
                if parts:
                    # Take the address that the last trusted proxy saw.
                    idx = max(0, len(parts) - self.hops)
                    real_ip = parts[idx]
                    if real_ip:
                        request.META['REMOTE_ADDR'] = real_ip
        return self.get_response(request)
