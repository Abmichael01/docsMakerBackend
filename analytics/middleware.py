import uuid
from django.utils import timezone
from .models import VisitorLog
from .utils import get_visitor_session_key

class VisitorTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.bot_keywords = [
            'bot', 'spider', 'crawler', 'lighthouse', 'google', 'bing', 
            'yandex', 'baiduspider', 'slurp', 'pingdom', 'uptime',
            'headless', 'python-requests', 'node-fetch', 'axios', 
            'postman', 'curl', 'wget', 'go-http', 'java', 'libwww-perl', 'ruby'
        ]

    def __call__(self, request):
        # 1. Identity Management (Standardized Persistent VUID)
        vuid = request.COOKIES.get('vux_id')
        new_vuid_created = False
        if not vuid:
            vuid = str(uuid.uuid4())
            new_vuid_created = True

        request.vuid = vuid
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        request.is_bot = self.is_bot(user_agent)

        response = self.get_response(request)

        # 2. Persist the identity cookie for 1 year
        if new_vuid_created:
            response.set_cookie(
                'vux_id', 
                vuid, 
                max_age=365*24*60*60, 
                httponly=True, 
                samesite='Lax'
            )

        # NOTE: We NO LONGER log every request here.
        # Visits are now logged explicitly via the frontend tracker to avoid noise.
        
        return response

    def is_bot(self, user_agent):
        if not user_agent:
            return True
        ua_lower = user_agent.lower()
        return any(keyword in ua_lower for keyword in self.bot_keywords)
