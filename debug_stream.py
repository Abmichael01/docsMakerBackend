import os
import json
import asyncio
from django.test import RequestFactory
from django.contrib.auth import get_user_model

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "serverConfig.settings")
import django
django.setup()

from asgiref.sync import sync_to_async
from api.views.ai_chat import AiChatView

User = get_user_model()

async def debug_stream():
    user, _ = await sync_to_async(User.objects.get_or_create)(username="debug_user")
    factory = RequestFactory()
    view = AiChatView()
    
    body = {
        "messages": [{"role": "user", "content": "Remove the background from my profile picture."}],
        "image_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
        "template_id": "00000000-0000-0000-0000-000000000000",
        "fields": [],
        "current_values": {}
    }
    
    req_data = json.dumps(body).encode("utf-8")
    request = factory.post("/api/ai-chat/", data=req_data, content_type="application/json")
    request.user = user
    request._body = req_data
    
    response = await view.post(request)
    print("--- RAW STREAM ---")
    async for chunk in response.streaming_content:
        print(chunk.decode("utf-8"), end="")
    print("\n--- END STREAM ---")

if __name__ == "__main__":
    asyncio.run(debug_stream())
