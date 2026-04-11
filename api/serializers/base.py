from rest_framework import serializers
from ..models import Tool, Font, TransformVariable, SiteSettings
from api.utils import get_signed_url

class FieldUpdateSerializer(serializers.Serializer):
    id = serializers.CharField()
    value = serializers.JSONField(required=False, allow_null=True)


class ToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tool
        fields = '__all__'


class TransformVariableSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransformVariable
        fields = '__all__'


class FontSerializer(serializers.ModelSerializer):
    font_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Font
        fields = ['id', 'name', 'family', 'weight', 'style', 'font_file', 'font_url', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_font_url(self, obj):
        """Return signed URL for the font file."""
        if obj.font_file:
            return get_signed_url(obj.font_file)
        return None


class SiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        fields = '__all__'
        read_only_fields = ['id', 'updated_at', 'template_cache_version']


class PublicSiteSettingsSerializer(serializers.ModelSerializer):
    """Serializer for guest users only showing non-sensitive configuration."""
    class Meta:
        model = SiteSettings
        fields = [
            'whatsapp_number', 'whatsapp_community_link', 'support_email',
            'telegram_link', 'twitter_link', 'instagram_link', 'tiktok_link',
            'min_topup_amount', 'funding_whatsapp_number', 'exchange_rate_override',
            'maintenance_mode', 'disable_new_signups', 'disable_deposits',
            'global_announcement_text', 'global_announcement_link', 'enable_global_announcement',
            'dev_name_obfuscated', 'owner_name_obfuscated', 'template_cache_version',
            'show_whatsapp_on_hover', 'show_community_on_hover', 'show_telegram_on_hover',
            'show_instagram_on_hover', 'show_twitter_on_hover', 'show_tiktok_on_hover'
        ]
        read_only_fields = fields

