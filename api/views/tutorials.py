from django.db.models import Q
from rest_framework import viewsets
from ..models import Tutorial
from ..serializers import TutorialSerializer
from ..permissions import IsAdminOrReadOnly

class TutorialViewSet(viewsets.ModelViewSet):
    queryset = Tutorial.objects.select_related('template', 'template__tool', 'tool').all()
    serializer_class = TutorialSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        template_id = self.request.query_params.get('template')
        tool_id = self.request.query_params.get('tool')
        search = self.request.query_params.get('search')
        featured = self.request.query_params.get('featured')

        if template_id:
            queryset = queryset.filter(template_id=template_id)
        if tool_id:
            # Tool-scoped tutorials and tutorials of templates under that tool
            queryset = queryset.filter(Q(tool_id=tool_id) | Q(template__tool_id=tool_id))
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(tool__name__icontains=search)
                | Q(template__name__icontains=search)
                | Q(template__tool__name__icontains=search)
            )
        if featured is not None:
            queryset = queryset.filter(is_featured=featured.lower() == 'true')
        return queryset
