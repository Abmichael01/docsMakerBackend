import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

class WalletConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if self.scope["user"].is_anonymous:
            await self.close()
        else:
            self.user = self.scope["user"]
            self.group_name = f"user_wallet_{self.user.id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()

            # Send initial wallet state
            wallet_data = await self.get_wallet_data()
            await self.send(text_data=json.dumps({
                "type": "wallet.updated",
                "data": wallet_data,
            }))

    async def disconnect(self, close_code):
        # Only discard if group_name was set (i.e., user was authenticated)
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    @database_sync_to_async
    def get_wallet_data(self):
        from wallet.serializers import WalletSerializer
        from wallet.models import Wallet
        wallet = Wallet.objects.get(user=self.user)
        return WalletSerializer(wallet).data

    async def wallet_updated(self, event):
        await self.send(text_data=json.dumps({
            "type": "wallet.updated",
            "data": event["data"],
        }))
