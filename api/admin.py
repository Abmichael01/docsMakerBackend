from django.contrib import admin
from django.contrib import messages
from .models import Tool, Template, PurchasedTemplate, SiteSettings

@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'id', 'hot', 'is_active', 'created_at')
    list_filter = ('hot', 'is_active', 'tool')
    search_fields = ('name', 'id')

    def delete_model(self, request, obj):
        # Count purchased templates before deletion
        purchased_count = obj.purchases.count()
        super().delete_model(request, obj)
        
        if purchased_count > 0:
            messages.warning( 
                request, 
                f"Template '{obj.name}' deleted successfully. {purchased_count} purchased template(s) are now orphaned but preserved."
            )
        else:
            messages.success(request, f"Template '{obj.name}' deleted successfully.")
    
    def delete_queryset(self, request, queryset):
        total_purchased = 0
        for obj in queryset:
            total_purchased += obj.purchases.count()
        
        super().delete_queryset(request, queryset)
        
        if total_purchased > 0:
            messages.warning(
                request,
                f"Templates deleted successfully. {total_purchased} purchased template(s) are now orphaned but preserved."
            )
        else:
            messages.success(request, f"Templates deleted successfully.")

# Register other models
admin.site.register(Tool)
admin.site.register(PurchasedTemplate)
admin.site.register(SiteSettings)