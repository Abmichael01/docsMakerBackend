from django.db import models
from django.conf import settings
from django.utils import timezone


class VisitorLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    visitor_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)  # Persistent cookie ID
    is_bot = models.BooleanField(default=False)
    path = models.CharField(max_length=255)

    method = models.CharField(max_length=10)
    user_agent = models.TextField(null=True, blank=True)
    referrer = models.TextField(null=True, blank=True)
    source = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    medium = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    campaign = models.CharField(max_length=150, null=True, blank=True, db_index=True)
    term = models.CharField(max_length=150, null=True, blank=True)
    content = models.CharField(max_length=150, null=True, blank=True)
    source_platform = models.CharField(max_length=100, null=True, blank=True)
    gclid = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    fbclid = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    channel_group = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['session_key']),
            models.Index(fields=['visitor_id']),
        ]

        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.ip_address} - {self.path} - {self.timestamp}"


class Campaign(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="Admin-facing label for this tracking campaign")
    description = models.TextField(null=True, blank=True)
    source = models.CharField(max_length=100, null=True, blank=True, db_index=True, help_text="UTM source, e.g. instagram, google, newsletter")
    medium = models.CharField(max_length=100, null=True, blank=True, db_index=True, help_text="UTM medium, e.g. social, paid_social, email")
    campaign = models.CharField(max_length=150, null=True, blank=True, db_index=True, help_text="UTM campaign name")
    content = models.CharField(max_length=150, null=True, blank=True, help_text="Optional UTM content value")
    term = models.CharField(max_length=150, null=True, blank=True, help_text="Optional UTM term value")
    source_platform = models.CharField(max_length=100, null=True, blank=True, help_text="Optional UTM source platform value")
    gclid = models.CharField(max_length=255, null=True, blank=True, help_text="Optional Google Click ID")
    fbclid = models.CharField(max_length=255, null=True, blank=True, help_text="Optional Facebook Click ID")
    landing_path = models.CharField(max_length=255, default='/', blank=True, help_text="Relative landing path for the generated tracking URL")
    ref_code = models.CharField(max_length=100, null=True, blank=True, help_text="Optional referral code to attach")
    created_at = models.DateTimeField(auto_now_add=True)
    last_visit_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=50)  # e.g., "DELETE_FONT", "UPDATE_SETTINGS"
    target = models.CharField(max_length=255)  # e.g., "Roboto (ID: 5)"
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict, blank=True)  # Extra info like changed fields

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

    def __str__(self):
        return f"{self.actor} - {self.action}"
