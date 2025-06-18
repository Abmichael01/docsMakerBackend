from rest_framework.routers import DefaultRouter
from .views import TemplateViewSet, PurchasedTemplateViewSet

router = DefaultRouter()
router.register(r'templates', TemplateViewSet, basename='template')
router.register(r'purchased-templates', PurchasedTemplateViewSet, basename='purchased-template')

urlpatterns = router.urls
