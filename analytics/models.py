from django.db import models
from django.conf import settings

class VisitorLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    path = models.CharField(max_length=255)
    method = models.CharField(max_length=10)
    user_agent = models.TextField(null=True, blank=True)
    referrer = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['session_key']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.ip_address} - {self.path} - {self.timestamp}"
