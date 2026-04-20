from django.utils import timezone
from datetime import timedelta
from .models import VisitorLog

class VisitorTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        
        # Exclude static, media, admin, and analytics API itself
        if any(path.startswith(prefix) for prefix in ['/static/', '/media/', '/admin/', '/api/analytics/']):
            return self.get_response(request)

        # Log visit (heartbeat approach)
        self.log_visit(request)

        return self.get_response(request)

    def log_visit(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
            
        session_key = request.session.session_key
        if not session_key:
            try:
                request.session.save()
                session_key = request.session.session_key
            except:
                pass 

        # Look for a recent log from this session (last 30 minutes)
        thirty_min_ago = timezone.now() - timedelta(minutes=30)
        
        existing_log = VisitorLog.objects.filter(
            session_key=session_key,
            ip_address=ip,
            timestamp__gt=thirty_min_ago
        ).order_by('-timestamp').first()

        if existing_log:
            # Refresh the existing heartbeat
            existing_log.timestamp = timezone.now()
            existing_log.path = request.path_info[:255]
            existing_log.method = request.method
            # Update user if they just logged in
            if not existing_log.user and request.user.is_authenticated:
                existing_log.user = request.user
            existing_log.save()
        else:
            # Create a new session entry
            VisitorLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                ip_address=ip,
                session_key=session_key,
                path=request.path_info[:255],
                method=request.method,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:1000] if request.META.get('HTTP_USER_AGENT') else '',
                referrer=request.META.get('HTTP_REFERER', '')[:1000] if request.META.get('HTTP_REFERER') else ''
            )
