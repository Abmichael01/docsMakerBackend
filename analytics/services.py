from datetime import timedelta

from django.utils import timezone

from .models import Campaign, VisitorLog
from .serializers import VisitorLogSerializer
from .utils import (
    build_source_label,
    get_attribution_for_request,
    get_client_ip,
    get_persistent_visitor_id,
    get_visitor_session_key,
    normalize_attribution,
)


def get_attribution_for_scope(scope, override_attribution=None, referrer=None):
    attribution_payload = override_attribution if isinstance(override_attribution, dict) else {}
    return normalize_attribution(attribution_payload, referrer=referrer)


def build_visitor_payload(log_instance):
    serialized_log = VisitorLogSerializer(log_instance).data
    return {
        **serialized_log,
        "user__username": log_instance.user.username if log_instance.user else None,
        "source_label": build_source_label(log_instance.source, log_instance.medium),
        "visit_count": 1,
    }


def update_legacy_campaign(source, attribution, path):
    legacy_campaign, _created = Campaign.objects.get_or_create(
        name=source[:100],
        defaults={
            'description': 'Auto-detected through legacy custom traffic links',
            'source': source[:100],
            'medium': (attribution.get('medium') or 'custom')[:100],
            'campaign': attribution.get('campaign'),
            'content': attribution.get('content'),
            'term': attribution.get('term'),
            'source_platform': attribution.get('source_platform'),
            'gclid': attribution.get('gclid'),
            'fbclid': attribution.get('fbclid'),
            'landing_path': path[:255] or '/',
        }
    )
    legacy_updates = ['last_visit_at']
    legacy_campaign.last_visit_at = timezone.now()

    for field_name, fallback in (
        ('source', source[:100]),
        ('medium', (attribution.get('medium') or 'custom')[:100]),
        ('campaign', attribution.get('campaign')),
        ('content', attribution.get('content')),
        ('term', attribution.get('term')),
        ('source_platform', attribution.get('source_platform')),
        ('gclid', attribution.get('gclid')),
        ('fbclid', attribution.get('fbclid')),
        ('landing_path', path[:255] or '/'),
    ):
        if not getattr(legacy_campaign, field_name) and fallback:
            setattr(legacy_campaign, field_name, fallback)
            legacy_updates.append(field_name)

    legacy_campaign.save(update_fields=legacy_updates)


def record_visit(*, path, attribution_payload=None, request=None, scope=None, referrer=None, user=None, visitor_id=None, is_bot=False):
    path = (path or '')[:500]
    if not path:
        return None, None

    if request is not None:
        ip = get_client_ip(request=request)
        session_key = get_visitor_session_key(request=request)
        attribution = get_attribution_for_request(request, override_attribution=attribution_payload)
        user_obj = getattr(request, 'user', None)
        resolved_user = user_obj if (user_obj and user_obj.is_authenticated) else None
        resolved_visitor_id = visitor_id or getattr(request, 'vuid', None)
        resolved_is_bot = getattr(request, 'is_bot', is_bot)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:1000]
    else:
        ip = get_client_ip(scope=scope)
        session_key = get_visitor_session_key(scope=scope)
        attribution = get_attribution_for_scope(scope, override_attribution=attribution_payload, referrer=referrer)
        resolved_user = user if user and getattr(user, 'is_authenticated', False) else None
        resolved_visitor_id = visitor_id or get_persistent_visitor_id(scope=scope) or session_key
        resolved_is_bot = is_bot
        headers = dict(scope.get('headers', [])) if scope else {}
        user_agent = headers.get(b'user-agent', b'').decode('utf-8', errors='ignore')[:1000] if headers else ''

    try:
        source = attribution['source']
        fifteen_mins_ago = timezone.now() - timedelta(minutes=15)

        existing = VisitorLog.objects.filter(
            visitor_id=resolved_visitor_id,
            path=path,
            timestamp__gt=fifteen_mins_ago
        ).first()

        if existing:
            updated_fields = ['timestamp']
            existing.timestamp = timezone.now()
            if resolved_user and not existing.user:
                existing.user = resolved_user
                updated_fields.append('user')
            
            # Special logic: If existing was 'direct' or '(not set)' but incoming is better, overwrite.
            for field_name in ('referrer', 'source', 'medium', 'campaign', 'term', 'content', 'source_platform', 'channel_group', 'gclid', 'fbclid'):
                incoming_value = attribution.get(field_name)
                current_value = getattr(existing, field_name)
                
                is_better = False
                if incoming_value:
                    if not current_value:
                        is_better = True
                    elif field_name == 'source' and current_value == 'direct':
                        is_better = True
                    elif field_name == 'medium' and current_value in ('(none)', '(not set)', 'custom'):
                        is_better = True
                    elif field_name == 'channel_group' and current_value in ('Direct', 'Unassigned'):
                        is_better = True

                if is_better:
                    setattr(existing, field_name, incoming_value)
                    if field_name not in updated_fields:
                        updated_fields.append(field_name)
            
            existing.save(update_fields=updated_fields)
            log_instance = existing
        else:
            log_instance = VisitorLog.objects.create(
                user=resolved_user,
                ip_address=ip,
                session_key=session_key,
                visitor_id=resolved_visitor_id,
                is_bot=resolved_is_bot,
                path=path,
                method='VIEW',
                user_agent=user_agent,
                referrer=attribution.get('referrer'),
                source=source,
                medium=attribution.get('medium'),
                campaign=attribution.get('campaign'),
                term=attribution.get('term'),
                content=attribution.get('content'),
                source_platform=attribution.get('source_platform'),
                gclid=attribution.get('gclid'),
                fbclid=attribution.get('fbclid'),
                channel_group=attribution.get('channel_group'),
            )

        if attribution.get('is_custom_source') and source:
            update_legacy_campaign(source, attribution, path)

        return log_instance, build_visitor_payload(log_instance)

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to record visit for path {path}: {str(e)}", exc_info=True)
        # Fallback to prevent app crash
        return None, None
