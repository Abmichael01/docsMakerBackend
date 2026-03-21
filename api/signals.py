from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from .models import Template
from .cache_utils import invalidate_template_cache
from .compression import compress_image
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Template)
def invalidate_cache_on_save(sender, instance, **kwargs):
    """
    Invalidate all template-related caches when a template is saved.
    This ensures that:
    1. The template list is updated (e.g. if a new template is added or hot status changed)
    2. The template detail is updated
    3. The SVG content is updated
    """
    logger.info(f"Signal: Template {instance.id} saved. Invalidating all template caches.")
    invalidate_template_cache()

@receiver(post_delete, sender=Template)
def invalidate_cache_on_delete(sender, instance, **kwargs):
    """
    Invalidate all template-related caches when a template is deleted.
    """
    logger.info(f"Signal: Template {instance.id} deleted. Invalidating all template caches.")
    invalidate_template_cache()

@receiver(pre_save, sender=Template)
def compress_template_images(sender, instance, **kwargs):
    """
    Compress banners before saving to storage.
    """
    if instance.banner:
        # Check if this is a new file or if the file has changed
        try:
            old_instance = Template.objects.get(pk=instance.pk)
            if old_instance.banner != instance.banner:
                compress_image(instance.banner)
        except Template.DoesNotExist:
            # New instance
            compress_image(instance.banner)
