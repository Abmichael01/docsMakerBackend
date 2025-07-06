from rest_framework.routers import DefaultRouter
from .views import *
from django.urls import path

router = DefaultRouter()
router.register(r'templates', TemplateViewSet, basename='template')
router.register(r'purchased-templates', PurchasedTemplateViewSet, basename='purchased-template')

urlpatterns = [
    path("track/<str:tracking_id>/", PublicTemplateTrackingView.as_view(), name="track-template"),
    path("download-doc/", DownloadDoc.as_view(), name="download-doc"),
]
urlpatterns += router.urls
