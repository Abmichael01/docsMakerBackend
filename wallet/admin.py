from django.contrib import admin
from .models import *
# Register your models here.


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'referral_balance')
    search_fields = ('user__username', 'user__email')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'wallet', 'type', 'amount', 'status', 'created_at')
    list_filter = ('type', 'status', 'created_at')
    search_fields = ('wallet__user__username', 'tx_hash', 'tx_id', 'description')

@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'user__email', 'usdt_address')