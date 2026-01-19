from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AnalyticsDashboardView, LogVisitView, AuditLogViewSet

router = DefaultRouter()
router.register(r'audit-logs', AuditLogViewSet, basename='audit-log')

urlpatterns = [
    path('dashboard/', AnalyticsDashboardView.as_view(), name='analytics-dashboard'),
    path('log-visit/', LogVisitView.as_view(), name='analytics-log-visit'),
    path('', include(router.urls)),
]
