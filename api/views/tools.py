from rest_framework import viewsets
from ..models import Tool
from ..serializers import ToolSerializer
from ..permissions import IsAdminOrReadOnly

class ToolViewSet(viewsets.ModelViewSet):
    queryset = Tool.objects.all().order_by('name')
    serializer_class = ToolSerializer
    permission_classes = [IsAdminOrReadOnly]
