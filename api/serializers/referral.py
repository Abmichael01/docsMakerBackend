from rest_framework import serializers
from api.models import Referral
from django.contrib.auth import get_user_model

User = get_user_model()

class ReferralSerializer(serializers.ModelSerializer):
    referred_username = serializers.CharField(source='referred_user.username', read_only=True)
    referred_email = serializers.EmailField(source='referred_user.email', read_only=True)
    
    class Meta:
        model = Referral
        fields = [
            'id', 
            'referred_username', 
            'referred_email', 
            'is_rewarded', 
            'reward_amount', 
            'created_at'
        ]
