from django.db import models
from django.contrib.auth import get_user_model
import uuid


User = get_user_model()

class Template(models.Model):
    TEMPLATE_TYPE_CHOICES = [
        ('tool', 'Tool'),
        ('graphic', 'Graphic'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    svg = models.TextField(default="")
    type = models.CharField(max_length=20, choices=TEMPLATE_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
        
    
class PurchasedTemplate(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relations
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="purchased_templates")
    template = models.ForeignKey("Template", on_delete=models.CASCADE, related_name="purchases")

    # Editable SVG and test mode
    svg = models.TextField()  # Stores the user-modified SVG
    test = models.BooleanField(default=False, help_text="True if user is previewing template without purchase")

    # Optional metadata
    tracking_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.buyer.username} - {self.template.name} ({'test' if self.test else 'paid'})"

