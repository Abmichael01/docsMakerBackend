from rest_framework.routers import DefaultRouter
from .views import *
from .views_admin import AdminOverview, AdminUsers, AdminUserDetails
from django.urls import path

router = DefaultRouter()
router.register(r'tools', ToolViewSet, basename='tool')
router.register(r'templates', TemplateViewSet, basename='template')
router.register(r'purchased-templates', PurchasedTemplateViewSet, basename='purchased-template')

urlpatterns = [
    path("track/<str:tracking_id>/", PublicTemplateTrackingView.as_view(), name="track-template"),
    path("download-doc/", DownloadDoc.as_view(), name="download-doc"),

    # Admin views
    path("admin/overview/", AdminOverview.as_view(), name="admin-overview"),
    path("admin/users/", AdminUsers.as_view(), name="admin-users"),
    path("admin/users/<int:user_id>/", AdminUserDetails.as_view(), name="admin-user-details"),
]
urlpatterns += router.urls
