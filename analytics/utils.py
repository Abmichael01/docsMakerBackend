from .models import AuditLog

def log_action(actor, action, target, ip_address=None, details=None):
    """
    Log an administrative action.
    """
    if not actor.is_authenticated:
        actor = None
        
    AuditLog.objects.create(
        actor=actor,
        action=action,
        target=target,
        ip_address=ip_address,
        details=details or {}
    )
