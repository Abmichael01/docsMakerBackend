# templates/serializers.py
from rest_framework import serializers
from django.db.models import Sum, Count
from django.contrib.auth import get_user_model
from api.watermark import WaterMark
from .models import Template, PurchasedTemplate, Tool, Tutorial, Font
from wallet.models import Wallet
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from datetime import timedelta
from accounts.serializers import CustomUserDetailsSerializer

User = get_user_model()


class ToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tool
        fields = '__all__'


class FontSerializer(serializers.ModelSerializer):
    font_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Font
        fields = ['id', 'name', 'font_file', 'font_url', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_font_url(self, obj):
        """Return absolute URL for font file"""
        request = self.context.get('request')
        if obj.font_file and request:
            return request.build_absolute_uri(obj.font_file.url)
        return obj.font_file.url if obj.font_file else None


class AdminOverviewSerializer(serializers.Serializer):
    total_downloads = serializers.IntegerField()
    total_users = serializers.IntegerField()
    total_purchased_docs = serializers.IntegerField()
    total_wallet_balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    
    def get_total_downloads(self):
        """Get total downloads across all users"""
        return User.objects.aggregate(
            total=Sum('downloads')
        )['total'] or 0
    
    def get_total_users(self):
        """Get total number of users"""
        return User.objects.count()
    
    def get_total_purchased_docs(self):
        """Get total number of paid documents (excluding test documents)"""
        return PurchasedTemplate.objects.filter(
            test=False  # Only count paid documents, not test ones
        ).count()
    
    def get_total_wallet_balance(self):
        """Get total wallet balance across all users"""
        return Wallet.objects.aggregate(
            total=Sum('balance')
        )['total'] or 0


class AdminUsersSerializer(serializers.Serializer):
    """Serializer specifically for Admin Users page"""
    all_users = serializers.IntegerField()
    new_users = serializers.DictField()
    total_purchases_users = serializers.DictField()
    users = serializers.ListField()
    
    def get_all_users(self):
        """Get total number of users"""
        return User.objects.count()
    
    def get_new_users_stats(self):
        """Get new users statistics for different time periods"""
        now = timezone.now()
        
        # Calculate date ranges
        today = now.date()
        seven_days_ago = today - timedelta(days=7)
        fourteen_days_ago = today - timedelta(days=14)
        thirty_days_ago = today - timedelta(days=30)
        
        # Count new users for each period
        today_users = User.objects.filter(date_joined__date=today).count()
        seven_days_users = User.objects.filter(date_joined__date__gte=seven_days_ago).count()
        fourteen_days_users = User.objects.filter(date_joined__date__gte=fourteen_days_ago).count()
        thirty_days_users = User.objects.filter(date_joined__date__gte=thirty_days_ago).count()
        
        return {
            'today': today_users,
            'past_7_days': seven_days_users,
            'past_14_days': fourteen_days_users,
            'past_30_days': thirty_days_users,
        }
    
    def get_total_purchases_users_stats(self):
        """Get users with purchases statistics for different time periods"""
        now = timezone.now()
        
        # Calculate date ranges
        today = now.date()
        seven_days_ago = today - timedelta(days=7)
        fourteen_days_ago = today - timedelta(days=14)
        thirty_days_ago = today - timedelta(days=30)
        
        # Count users with purchases for each period
        today_purchases = User.objects.filter(
            purchased_templates__test=False,
            purchased_templates__created_at__date=today
        ).distinct().count()
        
        seven_days_purchases = User.objects.filter(
            purchased_templates__test=False,
            purchased_templates__created_at__date__gte=seven_days_ago
        ).distinct().count()
        
        fourteen_days_purchases = User.objects.filter(
            purchased_templates__test=False,
            purchased_templates__created_at__date__gte=fourteen_days_ago
        ).distinct().count()
        
        thirty_days_purchases = User.objects.filter(
            purchased_templates__test=False,
            purchased_templates__created_at__date__gte=thirty_days_ago
        ).distinct().count()
        
        return {
            'today': today_purchases,
            'past_7_days': seven_days_purchases,
            'past_14_days': fourteen_days_purchases,
            'past_30_days': thirty_days_purchases,
        }
    
    def get_paginated_users(self, page=1, page_size=10):
        """Get paginated user data"""
        paginator = PageNumberPagination()
        paginator.page_size = page_size
        
        users = User.objects.all().order_by('-date_joined')
        paginated_users = paginator.paginate_queryset(users, None)
        
        user_serializer = CustomUserDetailsSerializer(paginated_users, many=True)
        return {
            'results': user_serializer.data,
            'count': paginator.page.paginator.count,
            'next': paginator.get_next_link(),
            'previous': paginator.get_previous_link(),
            'current_page': page,
            'total_pages': paginator.page.paginator.num_pages,
        }


class TutorialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tutorial
        fields = ['id', 'template', 'url', 'title', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class TemplateSerializer(serializers.ModelSerializer):
    tutorial = TutorialSerializer(read_only=True)
    fonts = FontSerializer(many=True, read_only=True)
    font_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Font.objects.all(),
        source='fonts',
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Template
        fields = '__all__'
    
    def create(self, validated_data):
        # Extract tutorial data from request data
        request = self.context.get('request')
        tutorial_url = request.data.get('tutorial_url') if request else None
        tutorial_title = request.data.get('tutorial_title') if request else None
        fonts_data = validated_data.pop('fonts', None)
        
        # Create the template
        template = Template.objects.create(**validated_data)
        
        if fonts_data:
            template.fonts.set(fonts_data)
        
        # Create tutorial if URL is provided
        if tutorial_url:
            Tutorial.objects.create(
                template=template,
                url=tutorial_url,
                title=tutorial_title or ''
            )
        
        return template
    
    def update(self, instance, validated_data):
        # Extract tutorial data from request data
        request = self.context.get('request')
        tutorial_url = request.data.get('tutorial_url') if request else None
        tutorial_title = request.data.get('tutorial_title') if request else None
        fonts_data = validated_data.pop('fonts', None)
        
        # Update the template
        instance = super().update(instance, validated_data)
        
        if fonts_data is not None:
            instance.fonts.set(fonts_data)
        
        # Update or create tutorial
        if tutorial_url is not None:  # Allow clearing tutorial by sending empty string
            tutorial, created = Tutorial.objects.get_or_create(
                template=instance,
                defaults={'url': tutorial_url, 'title': tutorial_title or ''}
            )
            if not created:
                tutorial.url = tutorial_url
                tutorial.title = tutorial_title or ''
                tutorial.save()
        
        return instance
        
    def to_representation(self, instance):
        # Get the base representation
        representation = super().to_representation(instance)
        request = self.context.get('request')
        view = self.context.get('view')
        
        # Handle banner URL for production
        if 'banner' in representation and representation['banner']:
            if request and hasattr(request, 'build_absolute_uri'):
                # Use request to build absolute URL
                representation['banner'] = request.build_absolute_uri(representation['banner'])
            else:
                # Fallback: check if we're in production
                from django.conf import settings
                if getattr(settings, 'ENV', 'development') == 'production':
                    # Use production domain
                    representation['banner'] = f"https://api.sharptoolz.com{representation['banner']}"
        
        if view and view.action == 'list':
            # For list view: remove SVG and form_fields, keep banner
            representation.pop('svg', None)
            representation.pop('form_fields', None)
            # Banner will be included automatically since it's in fields
        else:
            # For detail view: add watermark to SVG, keep banner
            if 'svg' in representation and representation['svg']:
                representation['svg'] = WaterMark().add_watermark(representation['svg'])
        
        return representation


class AdminTemplateSerializer(serializers.ModelSerializer):
    """Admin-only serializer that never adds watermarks to templates"""
    fonts = FontSerializer(many=True, read_only=True)
    font_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Font.objects.all(),
        source='fonts',
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Template
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')
    
    def create(self, validated_data):
        fonts_data = validated_data.pop('fonts', None)
        template = Template.objects.create(**validated_data)
        if fonts_data:
            template.fonts.set(fonts_data)
        return template
    
    def update(self, instance, validated_data):
        fonts_data = validated_data.pop('fonts', None)
        instance = super().update(instance, validated_data)
        if fonts_data is not None:
            instance.fonts.set(fonts_data)
        return instance
    
    def to_representation(self, instance):
        # Get the base representation
        representation = super().to_representation(instance)
        request = self.context.get('request')
        view = self.context.get('view')
        
        
        # Handle banner URL for production
        if 'banner' in representation and representation['banner']:
            if request and hasattr(request, 'build_absolute_uri'):
                # Use request to build absolute URL
                representation['banner'] = request.build_absolute_uri(representation['banner'])
            else:
                # Fallback: check if we're in production
                from django.conf import settings
                if getattr(settings, 'ENV', 'development') == 'production':
                    # Use production domain
                    representation['banner'] = f"https://api.sharptoolz.com{representation['banner']}"
        
        # For list view: remove SVG and form_fields, keep banner
        if view and view.action == 'list':
            representation.pop('svg', None)
            representation.pop('form_fields', None)
            # Banner will be included automatically since it's in fields
        else:
            # For detail view: keep SVG and form_fields WITHOUT watermarks
            # No watermark processing - admin gets clean templates
            pass
        
        return representation



class PurchasedTemplateSerializer(serializers.ModelSerializer):
    fonts = FontSerializer(source='template.fonts', many=True, read_only=True)
    banner = serializers.SerializerMethodField()
    
    class Meta:
        model = PurchasedTemplate
        fields = '__all__'
        read_only_fields = ('buyer',)
        
    def charge_if_test_false(self, instance, validated_data, is_update=False):
        old_test = instance.test if is_update else True  # Assume default True for new records
        new_test = validated_data.get("test", old_test)

        # Charge only if test changes from True to False
        if old_test is True and new_test is False:
            user = instance.buyer

            if not hasattr(user, "wallet"):
                raise serializers.ValidationError("User does not have a wallet.")

            charge_amount = 5
            if user.wallet.balance < charge_amount:
                raise serializers.ValidationError("Insufficient funds to remove watermark.")

            user.wallet.debit(charge_amount, description="Document purchase")

            # Remove watermark from SVG only when test changes from True to False
            svg = validated_data.get("svg")
            if svg:
                validated_data["svg"] = WaterMark().remove_watermark(svg)

    def update(self, instance, validated_data):
        self.charge_if_test_false(instance, validated_data, is_update=True)
        return super().update(instance, validated_data)

    def create(self, validated_data):
        # Create a temporary instance to simulate access to `buyer` and `test`
        temp_instance = self.Meta.model(**validated_data)
        self.charge_if_test_false(temp_instance, validated_data, is_update=False)
        
        # Copy keywords from template if not provided
        template = validated_data.get('template')
        if template and 'keywords' not in validated_data:
            validated_data['keywords'] = list(template.keywords) if template.keywords else []
        
        return super().create(validated_data)

    def to_representation(self, instance):
        # Get the base representation
        representation = super().to_representation(instance)
        request = self.context.get('request')
        view = self.context.get('view')
        
        # Remove heavy fields on list view and provide banner preview
        if view and view.action == 'list':
            representation.pop('form_fields', None)
            representation.pop('svg', None)
        else:
            # Add watermark to SVG if it's a test template (always add for purchased templates)
            if instance.test and 'svg' in representation:
                representation['svg'] = WaterMark().add_watermark(representation['svg'])
        
        return representation
    
    def get_banner(self, obj):
        template = obj.template
        if not template or not template.banner:
            return None
        request = self.context.get('request')
        banner_url = template.banner.url
        if request and hasattr(request, 'build_absolute_uri'):
            return request.build_absolute_uri(banner_url)
        return banner_url
    

    