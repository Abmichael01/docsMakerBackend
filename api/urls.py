from rest_framework.routers import DefaultRouter
from .views import (
    TemplateViewSet, AdminTemplateViewSet, PublicTemplateTrackingView,
    PurchasedTemplateViewSet, ToolViewSet, FontViewSet, SiteSettingsViewSet,
    TutorialViewSet, TransformVariableViewSet,
    DownloadDoc, RemoveBackgroundView, AdminOverview, AdminUsers, AdminUserDetails, AdminDocuments,
    WalletStatsView, WalletListView, WalletAdjustView, PendingRequestsView, ApproveRequestView, RejectRequestView, TransactionHistoryView
)
from django.urls import path

router = DefaultRouter()
router.register(r'tools', ToolViewSet, basename='tool')
router.register(r'templates', TemplateViewSet, basename='template')
router.register(r'admin/templates', AdminTemplateViewSet, basename='admin-template')
router.register(r'purchased-templates', PurchasedTemplateViewSet, basename='purchased-template')
router.register(r'tutorials', TutorialViewSet, basename='tutorial')
router.register(r'fonts', FontViewSet, basename='font')
router.register(r'settings', SiteSettingsViewSet, basename='settings')
router.register(r'transform-variables', TransformVariableViewSet, basename='transform-variable')

urlpatterns = [
    path("track/<str:tracking_id>/", PublicTemplateTrackingView.as_view(), name="track-template"),
    path("download-doc/", DownloadDoc.as_view(), name="download-doc"),
    path("remove-background/", RemoveBackgroundView.as_view(), name="remove-background"),

    # Admin views
    path("admin/overview/", AdminOverview.as_view(), name="admin-overview"),
    path("admin/users/", AdminUsers.as_view(), name="admin-users"),
    path("admin/users/<int:user_id>/", AdminUserDetails.as_view(), name="admin-user-details"),
    path("admin/documents/", AdminDocuments.as_view(), name="admin-documents"),
    
    # Admin Wallet Management
    path("admin/wallet/stats/", WalletStatsView.as_view(), name="admin-wallet-stats"),
    path("admin/wallet/", WalletListView.as_view(), name="admin-wallet-list"),
    path("admin/wallet/adjust/", WalletAdjustView.as_view(), name="admin-wallet-adjust"),
    path("admin/wallet/pending/", PendingRequestsView.as_view(), name="admin-wallet-pending"),
    path("admin/wallet/approve/", ApproveRequestView.as_view(), name="admin-wallet-approve"),
    path("admin/wallet/reject/", RejectRequestView.as_view(), name="admin-wallet-reject"),
    path("admin/wallet/transactions/", TransactionHistoryView.as_view(), name="admin-wallet-transactions"),
]
urlpatterns += router.urls
