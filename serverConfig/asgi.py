import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
from whitenoise import ASGIStaticFilesWrapper  # type: ignore # <- Important
from wallet.routing import websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'serverConfig.settings')
django.setup()

django_app = get_asgi_application()
application = ProtocolTypeRouter({
    "http": ASGIStaticFilesWrapper(django_app),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
