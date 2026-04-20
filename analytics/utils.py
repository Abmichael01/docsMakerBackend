def log_action(actor, action, target, ip_address=None, details=None):
    """
    Utility to record administrative actions in the AuditLog.
    Moving import inside to prevent premature model loading in ASGI/Channels.
    """
    from .models import AuditLog
    AuditLog.objects.create(
        actor=actor,
        action=action,
        target=target,
        ip_address=ip_address,
        details=details or {}
    )

def get_visitor_session_key(request=None, scope=None):
    """
    Standardized utility to generate a session key for visitors.
    Works for both Django HTTP requests and Channels WebSocket scopes.
    """
    if request:
        # For HTTP Middleware
        # Capturing IP (simplified for key generation)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')

        session_key = getattr(request.session, 'session_key', None)
        if not session_key:
            return f"anon-{ip}"
        return session_key

    if scope:
        # For WebSocket Consumers
        ip = scope['client'][0]
        
        # In Channels, the session is in scope['session']
        session = scope.get('session')
        session_key = session.session_key if session else None

        if not session_key:
            return f"anon-{ip}"
        return session_key
    
    return "unknown"
