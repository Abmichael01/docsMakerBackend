from rest_framework import viewsets
from ..models import Font
from ..serializers import FontSerializer
from ..permissions import IsAdminOrReadOnly
from analytics.utils import log_action

class FontViewSet(viewsets.ModelViewSet):
    queryset = Font.objects.all().order_by('name')
    serializer_class = FontSerializer
    permission_classes = [IsAdminOrReadOnly]

    def perform_create(self, serializer):
        font = serializer.save()
        log_action(
            actor=self.request.user,
            action="ADD_FONT",
            target=f"{font.family} ({font.pk})",
            ip_address=self.request.META.get('REMOTE_ADDR'),
            details={"style": font.style, "weight": font.weight}
        )

    def perform_destroy(self, instance):
        target_name = f"{instance.family} {instance.weight} {instance.style}"
        log_action(
            actor=self.request.user,
            action="DELETE_FONT",
            target=target_name,
            ip_address=self.request.META.get('REMOTE_ADDR')
        )
        instance.delete()
