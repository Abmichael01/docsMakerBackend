from django.contrib import admin
from .models import VisitorLog, Campaign, AuditLog

@admin.register(VisitorLog)
class VisitorLogAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'path', 'method', 'status_code', 'timestamp')
    list_filter = ('method', 'status_code', 'timestamp', 'source')
    search_fields = ('ip_address', 'path', 'user__username', 'session_key')

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'ref_code', 'created_at', 'last_visit_at')
    search_fields = ('name', 'ref_code')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('actor', 'action', 'target', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('actor__username', 'action', 'target')
