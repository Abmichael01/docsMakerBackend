from rest_framework import serializers
from wallet.models import Wallet, Transaction

class WalletSerializer(serializers.ModelSerializer):
    """Serializer for Wallet model"""
    user = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = ['id', 'user', 'balance', 'status', 'created_at']

    def get_user(self, obj):
        return {
            'id': obj.user.id,
            'username': obj.user.username,
            'email': obj.user.email,
        }

    def get_status(self, obj):
        # Wallet status is active by default (no blocked field in model yet)
        return 'active'

    def get_created_at(self, obj):
        # Use user's date_joined as wallet creation date
        return obj.user.date_joined.isoformat()


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for Transaction model"""
    user = serializers.SerializerMethodField()
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'user', 'type', 'amount', 
            'status', 'description', 'created_at'
        ]
    
    def get_user(self, obj):
        return {
            'id': obj.wallet.user.id,
            'username': obj.wallet.user.username,
            'email': obj.wallet.user.email,
        }
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Map Django field names to frontend expected names
        data['type'] = 'credit' if instance.type == 'deposit' else 'debit'
        data['balanceAfter'] = float(instance.wallet.balance)
        data['createdAt'] = instance.created_at.isoformat()
        data['status'] = instance.status
        return data
