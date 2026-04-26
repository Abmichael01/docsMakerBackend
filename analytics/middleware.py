import uuid
from .utils import is_bot_user_agent
from .services import record_visit, update_presence

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

        # 2. Smart Visit Tracking
        # The middleware only handles "Initial Landings" (requests with attribution).
        # Normal page views are handled by the frontend calling LogVisitView.
        if not request.is_bot:
            has_attribution = any(key in request.GET for key in [
                'utm_source', 'utm_medium', 'utm_campaign', 
                'source', 'medium', 'campaign',
                'gclid', 'fbclid', 'ref'
            ])
            
            if has_attribution:
                record_visit(
                    path=request.path,
                    request=request,
                    visitor_id=vuid
                )
            
            # 3. Active User Tracking (Presence)
            # Update the presence cache on every hit to keep the "Live" list accurate.
            update_presence(vuid, user=getattr(request, 'user', None))
        response = self.get_response(request)

        # 4. Persist the identity cookie for 1 year
        if new_vuid_created:
            response.set_cookie(
                'vux_id', 
                vuid, 
                max_age=365*24*60*60, 
                httponly=True, 
                samesite='Lax'
            )
        
        return response

