from rest_framework import viewsets
from ..models import Font
from ..serializers import FontSerializer
from ..permissions import IsAdminOrReadOnly

class FontViewSet(viewsets.ModelViewSet):
    queryset = Font.objects.all().order_by('name')
    serializer_class = FontSerializer
    permission_classes = [IsAdminOrReadOnly]
