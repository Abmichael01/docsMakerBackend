from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
import random

from ..models import SiteSettings
from ..serializers import SiteSettingsSerializer

class SiteSettingsViewSet(viewsets.ViewSet):
    """
    ViewSet for site configuration protected by email OTP (5-minute expiry).
    """
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return SiteSettings.get_settings()

    def list(self, request):
        settings_obj = self.get_object()
        serializer = SiteSettingsSerializer(settings_obj)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='request-code')
    def request_code(self, request):
        if not request.user.is_staff:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        
        # Generate 6-digit code
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        # Store in cache for 5 minutes (300 seconds)
        cache_key = f"admin_settings_otp_{request.user.id}"
        cache.set(cache_key, code, 300)
        
        # Send email
        try:
            subject = "Admin Settings Verification Code"
            message = f"Your verification code for updating site settings is: {code}. This code expires in 5 minutes."
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [settings.EMAIL_HOST_USER, "corehiseven@gmail.com"] # The owner's email from .env
            
            send_mail(subject, message, from_email, recipient_list)
            return Response({"message": "Verification code sent to email."})
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send verification email: {str(e)}")
            return Response({"error": f"Failed to send email: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def partial_update(self, request, pk=None):
        if not request.user.is_staff:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        settings_obj = self.get_object()
        
        # Verification Step: OTP
        otp = request.data.get('otp', '').strip()

        # OTP Verification from cache
        cache_key = f"admin_settings_otp_{request.user.id}"
        cached_otp = cache.get(cache_key)
        
        if not otp:
            return Response({"error": "Verification code is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        if not cached_otp or otp != cached_otp:
            return Response({"error": "Invalid or expired verification code."}, status=status.HTTP_403_FORBIDDEN)

        # Clear OTP after successful use
        cache.delete(cache_key)

        # Apply updates
        serializer = SiteSettingsSerializer(settings_obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
