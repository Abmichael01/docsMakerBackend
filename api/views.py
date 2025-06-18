# templates/views.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Template, PurchasedTemplate
from .serializers import TemplateSerializer, PurchasedTemplateSerializer
from .permissions import IsAdminOrReadOnly, IsOwnerOrAdmin


class TemplateViewSet(viewsets.ModelViewSet):
    queryset = Template.objects.all().order_by('-created_at')
    serializer_class = TemplateSerializer
    permission_classes = [IsAdminOrReadOnly]


class PurchasedTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = PurchasedTemplateSerializer
    permission_classes = [IsOwnerOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return PurchasedTemplate.objects.all().order_by('-created_at')
        return PurchasedTemplate.objects.filter(buyer=user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(buyer=self.request.user)
