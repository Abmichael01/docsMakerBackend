# urls.py
from django.urls import path, include
from .views import *


urlpatterns = [
    path('login/', LoginView.as_view()),
    path('logout/', LogoutView.as_view()),
    path('refresh-token/', RefreshTokenView.as_view(), name='token_refresh'),
    path('register/', RegisterView.as_view()),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password-confirm/", ResetPasswordConfirmView.as_view(), name="reset-password-confirm"),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    
    path('', include('dj_rest_auth.urls')),
    
]