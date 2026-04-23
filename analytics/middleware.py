import uuid
from .utils import is_bot_user_agent

class VisitorTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Identity Management (Standardized Persistent VUID)
        vuid = request.COOKIES.get('vux_id')
        new_vuid_created = False
        if not vuid:
            vuid = str(uuid.uuid4())
            new_vuid_created = True

        request.vuid = vuid
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        request.is_bot = is_bot_user_agent(user_agent)

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

