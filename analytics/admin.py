from django.contrib import admin
from .models import VisitorLog, Campaign, AuditLog


@admin.register(VisitorLog)
class VisitorLogAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'path', 'method', 'source', 'medium', 'channel_group', 'status_code', 'timestamp')
    list_filter = ('method', 'status_code', 'timestamp', 'source', 'medium', 'campaign', 'channel_group', 'is_bot')
    search_fields = ('ip_address', 'path', 'user__username', 'session_key', 'visitor_id', 'source', 'medium', 'campaign')


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'source', 'medium', 'campaign', 'ref_code', 'created_at', 'last_visit_at')
    list_filter = ('source', 'medium', 'created_at')
    search_fields = ('name', 'source', 'medium', 'campaign', 'ref_code')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('actor', 'action', 'target', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('actor__username', 'action', 'target')
