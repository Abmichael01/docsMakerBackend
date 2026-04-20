from django.utils import timezone
from datetime import timedelta
from .models import VisitorLog
from .utils import get_visitor_session_key

class VisitorTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Strict bot keywords in user agents
        self.bot_keywords = [
            'bot', 'spider', 'crawler', 'lighthouse', 'google', 'bing', 
            'yandex', 'baiduspider', 'slurp', 'pingdom', 'uptime',
            'headless', 'python-requests', 'node-fetch', 'axios', 
            'postman', 'curl', 'wget'
        ]

    def __call__(self, request):
        path = request.path_info
        
        # Broad Exclusions: static, media, admin, and analytics API itself
        if any(path.startswith(prefix) for prefix in ['/static/', '/media/', '/admin/', '/api/analytics/']):
            return self.get_response(request)

        # Process the request first to get the status code
        response = self.get_response(request)

        # Log visit after response is generated
        self.log_visit(request, response)

        return response

    def is_bot(self, user_agent):
        if not user_agent:
            # Assume requests without user agents in production might be bots/scripts
            return True
        ua_lower = user_agent.lower()
        return any(keyword in ua_lower for keyword in self.bot_keywords)

    def log_visit(self, request, response):
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # SKIP ALL BOTS - as requested
        if self.is_bot(user_agent):
            return

        # Capturing IP for the log
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
            
        # Use STANDARDIZED session key utility
        session_key = get_visitor_session_key(request=request)

        # Look for a recent heartbeat from this session (last 15 minutes)
        fifteen_min_ago = timezone.now() - timedelta(minutes=15)
        
        existing_log = VisitorLog.objects.filter(
            session_key=session_key,
            ip_address=ip,
            timestamp__gt=fifteen_min_ago
        ).order_by('-timestamp').first()

        if existing_log:
            # Refresh the existing heartbeat
            existing_log.timestamp = timezone.now()
            existing_log.path = request.path_info[:255]
            existing_log.method = request.method
            existing_log.status_code = response.status_code
            # Update user if they just logged in
            if not existing_log.user and request.user.is_authenticated:
                existing_log.user = request.user
            existing_log.save()
        else:
            # Create a new interaction entry
            VisitorLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                ip_address=ip,
                session_key=session_key,
                path=request.path_info[:255],
                method=request.method,
                status_code=response.status_code,
                user_agent=user_agent[:1000] if user_agent else '',
                referrer=request.META.get('HTTP_REFERER', '')[:1000] if request.META.get('HTTP_REFERER') else ''
            )
