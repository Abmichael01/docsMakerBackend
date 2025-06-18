# accounts/authentication.py
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.middleware import get_user
from django.http import JsonResponse

class JWTAuthenticationFromCookies(JWTAuthentication):
    def authenticate(self, request):
        access_token = request.COOKIES.get('access_token')
        if not access_token:
            return None

        validated_token = self.get_validated_token(access_token)
        user = self.get_user(validated_token)

        if not user or not user.is_active:
            raise AuthenticationFailed(_('User is inactive or deleted.'))

        return (user, validated_token)