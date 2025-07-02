from django.urls import path
from .views import *

urlpatterns = [
    path('wallet/', WalletDetailView.as_view(), name='wallet-detail'),
    path('create-payment/', CreateCryptoPaymentView.as_view(), name='create-crypto-payment'),
    path('cancel-payment/', CancelCryptoPaymentView.as_view(), name='cancel-crypto-payment'),
    path("webhook/cryptapi/", CryptAPIWebhookView.as_view(), name="cryptapi-webhook"),
]