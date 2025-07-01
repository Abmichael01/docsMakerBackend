from rest_framework import serializers
from wallet.models import Wallet, Transaction


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            'id', 'tx_id', 'type', 'amount', 'status',
            'description', 'tx_hash', 'address', 'created_at'
        ]


class WalletSerializer(serializers.ModelSerializer):
    transactions = TransactionSerializer(many=True, read_only=True)

    class Meta:
        model = Wallet
        fields = ['id', 'balance', 'transactions']
