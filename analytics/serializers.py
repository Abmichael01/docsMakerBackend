import re

from rest_framework import serializers
from .models import AuditLog, VisitorLog, Campaign


class CampaignSerializer(serializers.ModelSerializer):
    def _normalize_token(self, value):
        if value is None:
            return None

        value = str(value).strip().lower()
        if not value:
            return None

        value = re.sub(r'[^a-z0-9]+', '_', value)
        return value.strip('_') or None

    def validate(self, attrs):
        normalized_fields = ('source', 'medium', 'campaign', 'content', 'term', 'source_platform', 'ref_code', 'gclid', 'fbclid')

        for field in normalized_fields:
            if field in attrs:
                attrs[field] = self._normalize_token(attrs.get(field))

        if 'name' in attrs and attrs.get('name') is not None:
            attrs['name'] = str(attrs['name']).strip()

        landing_path = attrs.get('landing_path')
        if landing_path is not None:
            landing_path = str(landing_path).strip() or '/'
            if not landing_path.startswith('/'):
                landing_path = f'/{landing_path}'
            attrs['landing_path'] = landing_path

        for required_field in ('name', 'source', 'medium', 'campaign'):
            incoming_value = attrs.get(required_field)
            existing_value = getattr(self.instance, required_field, None) if self.instance else None
            if not incoming_value and not existing_value:
                raise serializers.ValidationError({required_field: 'This field is required.'})

        return attrs

    class Meta:
        model = Campaign
        fields = [
            'id',
            'name',
            'description',
            'source',
            'medium',
            'campaign',
            'content',
            'term',
            'source_platform',
            'gclid',
            'fbclid',
            'landing_path',
            'ref_code',
            'created_at',
            'last_visit_at',
        ]
        read_only_fields = ['created_at', 'last_visit_at']


class VisitorLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True, allow_null=True)

    class Meta:
        model = VisitorLog
        fields = [
            'id',
            'user',
            'username',
            'ip_address',
            'session_key',
            'visitor_id',
            'path',
            'method',
            'status_code',
            'user_agent',
            'referrer',
            'source',
            'medium',
            'campaign',
            'term',
            'content',
            'source_platform',
            'gclid',
            'fbclid',
            'channel_group',
            'timestamp',
        ]


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.username', read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'actor', 'actor_name', 'action', 'target', 'ip_address', 'timestamp', 'details']
