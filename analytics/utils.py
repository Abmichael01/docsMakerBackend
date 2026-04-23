import json
from urllib.parse import urlparse


def log_action(actor, action, target, ip_address=None, details=None):
    """
    Utility to record administrative actions in the AuditLog.
    Moving import inside to prevent premature model loading in ASGI/Channels.
    """
    from .models import AuditLog
    AuditLog.objects.create(
        actor=actor,
        action=action,
        target=target,
        ip_address=ip_address,
        details=details or {}
    )


def is_internal_referrer(referrer, current_host=None):
    referrer = clean_value(referrer, max_length=1000)
    current_host = clean_value(current_host, max_length=255)
    if not referrer or not current_host:
        return False

    try:
        hostname = (urlparse(referrer).hostname or '').lower()
    except ValueError:
        return False

    current_host = current_host.lower()
    return hostname == current_host or hostname.endswith(f".{current_host}")


def clean_value(value, max_length=255):
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    return value[:max_length]


def get_client_ip(request=None, scope=None):
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    if scope:
        headers = dict(scope.get('headers', []))
        x_forwarded_for = headers.get(b'x-forwarded-for')
        if x_forwarded_for:
            return x_forwarded_for.decode('utf-8').split(',')[0].strip()
        client = scope.get('client') or ('', 0)
        return client[0]

    return None


def get_visitor_session_key(request=None, scope=None):
    """
    Standardized utility to generate a session key for visitors.
    Works for both Django HTTP requests and Channels WebSocket scopes.
    """
    if request:
        ip = get_client_ip(request=request)

        session_key = getattr(request.session, 'session_key', None)
        if not session_key:
            return f"anon-{ip}"
        return session_key

    if scope:
        ip = get_client_ip(scope=scope)
        session = scope.get('session')
        session_key = session.session_key if session else None

        if not session_key:
            return f"anon-{ip}"
        return session_key

    return "unknown"


def classify_referrer(referrer):
    referrer = clean_value(referrer, max_length=1000)
    if not referrer:
        return {}

    try:
        hostname = urlparse(referrer).hostname or ''
    except ValueError:
        hostname = ''

    hostname = hostname.lower()
    if not hostname:
        return {}

    source = hostname
    medium = 'referral'
    channel_group = 'Referral'

    if 'google.' in hostname:
        source = 'google'
        medium = 'organic'
        channel_group = 'Organic Search'
    elif 'bing.' in hostname:
        source = 'bing'
        medium = 'organic'
        channel_group = 'Organic Search'
    elif 'duckduckgo.' in hostname:
        source = 'duckduckgo'
        medium = 'organic'
        channel_group = 'Organic Search'
    elif 'search.yahoo.' in hostname:
        source = 'yahoo'
        medium = 'organic'
        channel_group = 'Organic Search'
    elif 'yandex.' in hostname:
        source = 'yandex'
        medium = 'organic'
        channel_group = 'Organic Search'
    elif 'baidu.' in hostname:
        source = 'baidu'
        medium = 'organic'
        channel_group = 'Organic Search'
    elif 'facebook.com' in hostname or 'fb.' in hostname:
        source = 'facebook'
        medium = 'social'
        channel_group = 'Organic Social'
    elif 'instagram.com' in hostname:
        source = 'instagram'
        medium = 'social'
        channel_group = 'Organic Social'
    elif 'linkedin.com' in hostname:
        source = 'linkedin'
        medium = 'social'
        channel_group = 'Organic Social'
    elif 'twitter.com' in hostname or hostname == 'x.com' or 't.co' in hostname:
        source = 'x'
        medium = 'social'
        channel_group = 'Organic Social'
    elif 'reddit.com' in hostname:
        source = 'reddit'
        medium = 'social'
        channel_group = 'Organic Social'
    elif 'tiktok.com' in hostname:
        source = 'tiktok'
        medium = 'social'
        channel_group = 'Organic Social'
    elif 'pinterest.com' in hostname:
        source = 'pinterest'
        medium = 'social'
        channel_group = 'Organic Social'
    elif 'youtube.com' in hostname:
        source = 'youtube'
        medium = 'social'
        channel_group = 'Organic Social'

    return {
        'source': clean_value(source, max_length=100),
        'medium': medium,
        'channel_group': channel_group,
    }


def derive_channel_group(source, medium):
    source = (source or '').lower()
    medium = (medium or '').lower()

    if source == 'direct' or medium == '(none)':
        return 'Direct'
    if medium in ('organic', 'seo'):
        return 'Organic Search'
    if medium in ('social', 'social-network', 'social-media'):
        return 'Organic Social'
    if medium in ('paid_social', 'paidsocial'):
        return 'Paid Social'
    if medium in ('cpc', 'ppc', 'paidsearch', 'paid_search'):
        return 'Paid Search'
    if medium == 'email':
        return 'Email'
    if medium == 'affiliate':
        return 'Affiliate'
    if medium == 'display':
        return 'Display'
    if medium == 'referral':
        return 'Referral'
    if medium == 'custom':
        return 'Custom Campaign'
    return 'Unassigned'


def build_source_label(source, medium):
    normalized_source = clean_value(source, max_length=100) or 'direct'
    normalized_medium = clean_value(medium, max_length=100) or '(none)'
    return f"{normalized_source} / {normalized_medium}"


def parse_attribution_cookie(request):
    raw_cookie = request.COOKIES.get('traffic_attribution')
    legacy_source = clean_value(request.COOKIES.get('traffic_source'), max_length=100)

    if raw_cookie:
        try:
            cookie_data = json.loads(raw_cookie)
            if isinstance(cookie_data, dict):
                return cookie_data
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

    if legacy_source:
        return {
            'source': legacy_source,
            'medium': 'custom',
            'channel_group': 'Custom Campaign',
            'is_custom_source': True,
        }

    return {}


def normalize_attribution(attribution=None, referrer=None):
    payload = attribution if isinstance(attribution, dict) else {}

    source = clean_value(payload.get('source') or payload.get('utm_source'), max_length=100)
    medium = clean_value(payload.get('medium') or payload.get('utm_medium'), max_length=100)
    campaign = clean_value(payload.get('campaign') or payload.get('utm_campaign'), max_length=150)
    term = clean_value(payload.get('term') or payload.get('utm_term'), max_length=150)
    content = clean_value(payload.get('content') or payload.get('utm_content'), max_length=150)
    source_platform = clean_value(
        payload.get('source_platform') or payload.get('utm_source_platform'),
        max_length=100,
    )
    referrer = clean_value(
        payload.get('initial_referrer') or payload.get('referrer') or referrer,
        max_length=1000,
    )
    is_custom_source = bool(payload.get('is_custom_source'))

    if not source and referrer:
        inferred = classify_referrer(referrer)
        source = inferred.get('source')
        medium = medium or inferred.get('medium')
        channel_group = inferred.get('channel_group')
    else:
        channel_group = clean_value(payload.get('channel_group'), max_length=100)

    if source and not medium:
        medium = 'custom' if is_custom_source else '(not set)'

    if not source:
        source = 'direct'
        medium = medium or '(none)'

    if not channel_group:
        channel_group = derive_channel_group(source, medium)

    return {
        'source': source,
        'medium': medium,
        'campaign': campaign,
        'term': term,
        'content': content,
        'source_platform': source_platform,
        'channel_group': channel_group,
        'referrer': referrer,
        'is_custom_source': is_custom_source,
        'source_label': build_source_label(source, medium),
    }


def get_attribution_for_request(request, override_attribution=None):
    attribution_payload = override_attribution if isinstance(override_attribution, dict) else {}
    cookie_attribution = parse_attribution_cookie(request)
    merged_attribution = {**cookie_attribution, **attribution_payload}
    referrer = request.META.get('HTTP_REFERER')
    if is_internal_referrer(referrer, request.get_host()):
        referrer = None
    return normalize_attribution(merged_attribution, referrer=referrer)
