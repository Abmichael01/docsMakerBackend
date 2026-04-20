import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.cache import cache
from .utils import get_visitor_session_key

PRESENCE_CACHE_KEY = "online_visitor_sessions"

class ActivityConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Only allow authenticated staff/admin
        if self.scope["user"].is_anonymous or not self.scope["user"].is_staff:
            await self.close()
        else:
            self.group_name = "admin_activity"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            
            # INITIAL SYNC: Send the current list of online users immediately
            online_set = cache.get(PRESENCE_CACHE_KEY, set())
            await self.send(text_data=json.dumps({
                "type": "online_list",
                "sessions": list(online_set)
            }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def activity_event(self, event):
        await self.send(text_data=json.dumps(event["data"]))

    async def presence_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "presence_update",
            **event["data"]
        }))

class PresenceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = "global_presence"
        self.admin_group = "admin_activity"
        
        # Use STANDARDIZED session key utility
        self.session_key = get_visitor_session_key(scope=self.scope)
        user = self.scope["user"]
        self.username = user.username if user.is_authenticated else None
        
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        
        # Update server-side presence cache
        online_set = cache.get(PRESENCE_CACHE_KEY, set())
        online_set.add(self.session_key)
        cache.set(PRESENCE_CACHE_KEY, online_set, timeout=3600) # 1 hour rolling
        
        # Notify admins that a user is online
        await self.channel_layer.group_send(
            self.admin_group,
            {
                "type": "presence_update",
                "data": {
                    "status": "online",
                    "session_key": self.session_key,
                    "username": self.username,
                    "ip_address": self.scope['client'][0]
                }
            }
        )

    async def disconnect(self, close_code):
        # Update server-side presence cache
        online_set = cache.get(PRESENCE_CACHE_KEY, set())
        if self.session_key in online_set:
            online_set.remove(self.session_key)
        cache.set(PRESENCE_CACHE_KEY, online_set, timeout=3600)

        # Notify admins that a user is offline
        await self.channel_layer.group_send(
            self.admin_group,
            {
                "type": "presence_update",
                "data": {
                    "status": "offline",
                    "session_key": self.session_key,
                    "username": self.username,
                }
            }
        )
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
