import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.cache import cache
from asgiref.sync import sync_to_async
from .utils import get_persistent_visitor_id, get_visitor_session_key
from .services import record_visit

PRESENCE_CACHE_KEY = "online_visitor_sessions"


def load_presence_counts():
    cached_presence = cache.get(PRESENCE_CACHE_KEY, {}) or {}

    if isinstance(cached_presence, set):
        return {presence_key: 1 for presence_key in cached_presence}

    if isinstance(cached_presence, dict):
        return cached_presence

    return {}


@sync_to_async
def get_online_presence_keys():
    presence_counts = load_presence_counts()
    return list(presence_counts.keys())


@sync_to_async
def add_online_presence(presence_key):
    presence_counts = load_presence_counts()
    previous_count = int(presence_counts.get(presence_key, 0))
    presence_counts[presence_key] = previous_count + 1
    cache.set(PRESENCE_CACHE_KEY, presence_counts, timeout=3600)
    return previous_count == 0


@sync_to_async
def remove_online_presence(presence_key):
    presence_counts = load_presence_counts()
    previous_count = int(presence_counts.get(presence_key, 0))

    if previous_count <= 1:
        presence_counts.pop(presence_key, None)
        went_offline = previous_count > 0
    else:
        presence_counts[presence_key] = previous_count - 1
        went_offline = False

    cache.set(PRESENCE_CACHE_KEY, presence_counts, timeout=3600)
    return went_offline

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
            online_set = await get_online_presence_keys()
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
        
        self.session_key = get_visitor_session_key(scope=self.scope)
        self.presence_key = get_persistent_visitor_id(scope=self.scope) or self.session_key
        user = self.scope["user"]
        self.username = user.username if user.is_authenticated else None
        
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        
        # Track presence by a stable visitor id and keep tab/window counts.
        became_online = await add_online_presence(self.presence_key)
        
        # Extract real IP from headers for notification
        headers = dict(self.scope.get('headers', []))
        x_forwarded_for = headers.get(b'x-forwarded-for')
        real_ip = x_forwarded_for.decode('utf-8').split(',')[0] if x_forwarded_for else self.scope['client'][0]

        if became_online:
            # Notify admins only when the visitor's first tab connects.
            await self.channel_layer.group_send(
                self.admin_group,
                {
                    "type": "presence_update",
                    "data": {
                        "status": "online",
                        "presence_key": self.presence_key,
                        "username": self.username,
                        "ip_address": real_ip
                    }
                }
            )

    async def disconnect(self, close_code):
        went_offline = await remove_online_presence(self.presence_key)

        if went_offline:
            # Notify admins only after the visitor's last tab disconnects.
            await self.channel_layer.group_send(
                self.admin_group,
                {
                    "type": "presence_update",
                    "data": {
                        "status": "offline",
                        "presence_key": self.presence_key,
                        "username": self.username,
                    }
                }
            )
        await self.channel_layer.group_discard(self.group_name, self.channel_name)


class VisitorAnalyticsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"type": "error", "detail": "Invalid JSON payload"}))
            return

        event_type = payload.get("type")
        if event_type not in {"page_view", "heartbeat"}:
            await self.send(text_data=json.dumps({"type": "error", "detail": "Unsupported analytics event"}))
            return

        if event_type == "heartbeat":
            await self.send(text_data=json.dumps({"type": "heartbeat_ack"}))
            return

        path = payload.get("path", "")
        if not path:
            await self.send(text_data=json.dumps({"type": "error", "detail": "Path is required"}))
            return

        attribution = payload.get("attribution") or {}
        referrer = payload.get("referrer")
        user = self.scope.get("user")
        is_bot = False
        user_agent = dict(self.scope.get("headers", [])).get(b'user-agent', b'').decode('utf-8', errors='ignore').lower()
        if user_agent:
            is_bot = any(keyword in user_agent for keyword in ('bot', 'spider', 'crawler', 'headless', 'curl', 'wget'))

        _log_instance, visitor_payload = await sync_to_async(record_visit)(
            path=path,
            attribution_payload=attribution,
            scope=self.scope,
            referrer=referrer,
            user=user,
            visitor_id=get_persistent_visitor_id(scope=self.scope),
            is_bot=is_bot,
        )

        await self.channel_layer.group_send(
            "admin_activity",
            {
                "type": "activity_event",
                "data": {
                    "type": "new_visit",
                    "visitor": visitor_payload,
                }
            }
        )

        await self.send(text_data=json.dumps({"type": "visit_logged", "path": path}))
