from rest_framework import serializers
from .models import AuditLog, VisitorLog

class VisitorLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True, allow_null=True)

    class Meta:
        model = VisitorLog
        fields = ['id', 'user', 'username', 'ip_address', 'session_key', 'path', 'method', 'user_agent', 'referrer', 'timestamp']


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.username', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = ['id', 'actor', 'actor_name', 'action', 'target', 'ip_address', 'timestamp', 'details']
