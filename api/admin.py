from django.contrib import admin
from django.contrib import messages
from .models import Tool, Template, PurchasedTemplate, SiteSettings, Tutorial, Font, TransformVariable, AiChatSession, AiChatMessage, Referral

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

@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ('name', 'id', 'price', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'id')

@admin.register(PurchasedTemplate)
class PurchasedTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'buyer', 'template', 'created_at')
    list_filter = ('created_at', 'buyer')
    search_fields = ('name', 'buyer__username', 'buyer__email', 'tracking_id')

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'updated_at', 'maintenance_mode')

@admin.register(Tutorial)
class TutorialAdmin(admin.ModelAdmin):
    list_display = ('title', 'template', 'url')
    search_fields = ('title', 'url')

@admin.register(Font)
class FontAdmin(admin.ModelAdmin):
    list_display = ('name', 'family', 'weight', 'style')
    search_fields = ('name', 'family')

@admin.register(TransformVariable)
class TransformVariableAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'value', 'updated_at')
    list_filter = ('category',)
    search_fields = ('name',)

@admin.register(AiChatSession)
class AiChatSessionAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('title', 'user__username', 'user__email')

@admin.register(AiChatMessage)
class AiChatMessageAdmin(admin.ModelAdmin):
    list_display = ('session', 'role', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('content',)

@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ('referrer', 'referred_user', 'reward_amount', 'created_at')
    list_filter = ('is_rewarded', 'created_at')
    search_fields = ('referrer__username', 'referred_user__username')