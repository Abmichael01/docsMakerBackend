from rest_framework import serializers
from ..models import AiChatSession, AiChatMessage

class AiChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AiChatMessage
        fields = ['id', 'role', 'content', 'metadata', 'created_at']

class AiChatSessionSerializer(serializers.ModelSerializer):
    message_count = serializers.IntegerField(source='messages.count', read_only=True)
    
    class Meta:
        model = AiChatSession
        fields = ['id', 'title', 'template', 'purchased_template', 'message_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'message_count', 'created_at', 'updated_at']
