from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AnalyticsDashboardView, LogVisitView, AuditLogViewSet, UserActivityView

router = DefaultRouter()
router.register(r'audit-logs', AuditLogViewSet, basename='audit-log')

urlpatterns = [
    path('dashboard/', AnalyticsDashboardView.as_view(), name='analytics-dashboard'),
    path('user-activity/', UserActivityView.as_view(), name='user-activity'),
    path('log-visit/', LogVisitView.as_view(), name='analytics-log-visit'),
    path('', include(router.urls)),
]
