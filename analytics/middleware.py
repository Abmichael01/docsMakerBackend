from .models import VisitorLog
import time

class VisitorTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Process request
        response = self.get_response(request)
        
        # Log after response to ensure it wasn't a 404/500 if we care, 
        # but usually we want to log attempts too. 
        # Let's log if it's not a static/media file.
        
        path = request.path_info
        if not any(path.startswith(prefix) for prefix in ['/static/', '/media/', '/admin/']):
            # Also maybe skip some internal API polling if it exists
            self.log_visit(request)

        return response

    def log_visit(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
            
        # Get session key if available (even for anon)
        if not request.session.session_key:
            try:
                request.session.save()
            except:
                pass 
        session_key = request.session.session_key

        VisitorLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            ip_address=ip,
            session_key=session_key,
            path=request.path_info[:255],
            method=request.method,
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:1000] if request.META.get('HTTP_USER_AGENT') else '',
            referrer=request.META.get('HTTP_REFERER', '')[:1000] if request.META.get('HTTP_REFERER') else ''
        )
