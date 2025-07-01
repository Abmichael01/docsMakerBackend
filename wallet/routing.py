from django.urls import re_path
from .consumers import WalletConsumer

websocket_urlpatterns = [
    re_path(r"ws/wallet/$", WalletConsumer.as_asgi()),
]
