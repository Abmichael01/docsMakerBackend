from rest_framework import serializers
from .models import AuditLog, VisitorLog, Campaign

class CampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = ['id', 'name', 'description', 'ref_code', 'created_at', 'last_visit_at']
        read_only_fields = ['created_at', 'last_visit_at']

class VisitorLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True, allow_null=True)

    class Meta:
        model = VisitorLog
        fields = ['id', 'user', 'username', 'ip_address', 'session_key', 'path', 'method', 'status_code', 'user_agent', 'referrer', 'source', 'timestamp']


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.username', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = ['id', 'actor', 'actor_name', 'action', 'target', 'ip_address', 'timestamp', 'details']
