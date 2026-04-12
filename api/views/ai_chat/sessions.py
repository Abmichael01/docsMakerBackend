from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from ...models import AiChatSession, AiChatMessage
from ...serializers.ai_chat import AiChatSessionSerializer, AiChatMessageSerializer

class AiChatSessionViewSet(viewsets.ModelViewSet):
    serializer_class = AiChatSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        from ...models import SiteSettings
        if not SiteSettings.get_settings().enable_ai_features:
            self.permission_denied(request, message="AI Features are currently disabled by Admin.")
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        return AiChatSession.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        session = self.get_object()
        messages = session.messages.all()
        serializer = AiChatMessageSerializer(messages, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def clear(self, request, pk=None):
        session = self.get_object()
        session.messages.all().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
