from rest_framework import viewsets, permissions
from ..models import TransformVariable
from ..serializers import TransformVariableSerializer

class TransformVariableViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing reusable SVG transform values.
    """
    queryset = TransformVariable.objects.all()
    serializer_class = TransformVariableSerializer
    permission_classes = [permissions.IsAuthenticated] # Or IsAdminUser if you want to restrict to staff

    def get_queryset(self):
        # Allow filtering or ordering if needed
        return super().get_queryset().order_by('name')
