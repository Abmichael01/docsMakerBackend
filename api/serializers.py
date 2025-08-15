# templates/serializers.py
from rest_framework import serializers
from django.db.models import Sum, Count
from django.contrib.auth import get_user_model
from api.watermark import WaterMark
from .models import Template, PurchasedTemplate
from wallet.models import Wallet
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from datetime import timedelta
from accounts.serializers import CustomUserDetailsSerializer

User = get_user_model()


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


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Template
        fields = '__all__'
        
    def to_representation(self, instance):
        # Get the base representation
        representation = super().to_representation(instance)
        request = self.context.get('request')
        view = self.context.get('view')
        if view and view.action == 'list':
            representation.pop('form_fields', None)  # Remove it on list
        else:
            representation['svg'] = WaterMark().add_watermark(representation['svg'])
        
        return representation



class PurchasedTemplateSerializer(serializers.ModelSerializer):
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
            print("Charging ₦5 for watermark removal...")

    def update(self, instance, validated_data):
        self.charge_if_test_false(instance, validated_data, is_update=True)
        return super().update(instance, validated_data)

    def create(self, validated_data):
        # Create a temporary instance to simulate access to `buyer` and `test`
        temp_instance = self.Meta.model(**validated_data)
        self.charge_if_test_false(temp_instance, validated_data, is_update=False)
        return super().create(validated_data)

    def to_representation(self, instance):
        # Get the base representation
        representation = super().to_representation(instance)
        request = self.context.get('request')
        view = self.context.get('view')
        
        # Remove form_fields on list view
        if view and view.action == 'list':
            representation.pop('form_fields', None)
        
        # Add watermark to SVG if it's a test template
        if instance.test and 'svg' in representation:
            representation['svg'] = WaterMark().add_watermark(representation['svg'])
        
        return representation
    

    