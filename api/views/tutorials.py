from rest_framework import viewsets
from ..models import Tutorial
from ..serializers import TutorialSerializer
from ..permissions import IsAdminOrReadOnly

class TutorialViewSet(viewsets.ModelViewSet):
    queryset = Tutorial.objects.select_related('template', 'template__tool').all()
    serializer_class = TutorialSerializer
    permission_classes = [IsAdminOrReadOnly]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        template_id = self.request.query_params.get('template')
        tool_id = self.request.query_params.get('tool')
        
        if template_id:
            queryset = queryset.filter(template_id=template_id)
        if tool_id:
            queryset = queryset.filter(template__tool_id=tool_id)
        return queryset
