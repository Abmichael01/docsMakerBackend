from django.db.models.signals import post_save
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import VisitorLog
from .serializers import VisitorLogSerializer

@receiver(post_save, sender=VisitorLog)
def broadcast_activity(sender, instance, created, **kwargs):
    channel_layer = get_channel_layer()
    serializer = VisitorLogSerializer(instance)
    
    # Broadcast to the activity_admins group
    async_to_sync(channel_layer.group_send)(
        "admin_activity",
        {
            "type": "activity_event",
            "data": serializer.data
        }
    )
