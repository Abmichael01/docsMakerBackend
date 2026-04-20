from django.urls import re_path
from .consumers import ActivityConsumer, PresenceConsumer

websocket_urlpatterns = [
    re_path(r"ws/activity/$", ActivityConsumer.as_asgi()),
    re_path(r"ws/presence/$", PresenceConsumer.as_asgi()),
]
