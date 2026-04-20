import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

class ActivityConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Only allow authenticated staff/admin
        if self.scope["user"].is_anonymous or not self.scope["user"].is_staff:
            await self.close()
        else:
            self.group_name = "admin_activity"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def activity_event(self, event):
        """
        Called when a signal sends an 'activity_event' message to the group.
        """
        await self.send(text_data=json.dumps(event["data"]))
