# templates/views.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import *
from .serializers import *
from .permissions import *
from rest_framework.permissions import SAFE_METHODS
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class TemplateViewSet(viewsets.ModelViewSet):
    queryset = Template.objects.all().order_by('-created_at')
    serializer_class = TemplateSerializer
    permission_classes = [IsAdminOrReadOnly]
    # authentication_classes = []
    
    def get_authenticators(self):
        if self.request.method in SAFE_METHODS:
            return []  # No authentication for GET/HEAD/OPTIONS
        return super().get_authenticators()


class PurchasedTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = PurchasedTemplateSerializer
    permission_classes = [IsOwnerOrAdmin]

    def get_queryset(self): # type: ignore
        user = self.request.user
        if user.is_staff:
            return PurchasedTemplate.objects.all().order_by('-created_at')
        return PurchasedTemplate.objects.filter(buyer=user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(buyer=self.request.user)
        

class PublicTemplateTrackingView(APIView):
    permission_classes = [AllowAny]  # ✅ allows anyone
    authentication_classes = []      # ✅ disables auth

    def get(self, request, tracking_id):  # ✅ must include `request`
        try:
            purchased_template = PurchasedTemplate.objects.get(tracking_id=tracking_id)
            serializer = PurchasedTemplateSerializer(purchased_template)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except PurchasedTemplate.DoesNotExist:
            return Response({"detail": "Template not found."}, status=status.HTTP_404_NOT_FOUND)
