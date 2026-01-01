from django.urls import path
from .views import AnalyticsDashboardView, LogVisitView

urlpatterns = [
    path('dashboard/', AnalyticsDashboardView.as_view(), name='analytics-dashboard'),
    path('log-visit/', LogVisitView.as_view(), name='analytics-log-visit'),
]
