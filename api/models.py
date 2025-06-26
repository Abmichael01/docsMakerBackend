# models.py
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.postgres.fields import JSONField  # Use `models.JSONField` if Django 3.1+
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from .svg_parser import parse_svg_to_form_fields

User = get_user_model()



class Template(models.Model):
    TEMPLATE_TYPE_CHOICES = [
        ('tool', 'Tool'),
        ('design', 'Design'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    svg = models.TextField()
    form_fields = models.JSONField(default=dict, blank=True)
    type = models.CharField(max_length=20, choices=TEMPLATE_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.svg:
            self.form_fields = parse_svg_to_form_fields(self.svg)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class PurchasedTemplate(models.Model):
    STATUS_CHOICES = [
        ("", ""),
        ("processing", "Processing"),
        ("in_transit", "In Transit"),
        ("delivered", "Delivered"),
        ("error_message", "Error Message"),
    ]


    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="purchased_templates")
    template = models.ForeignKey("Template", on_delete=models.CASCADE, related_name="purchases")
    
    name = models.CharField(max_length=255, blank=True)

    svg = models.TextField()
    form_fields = models.JSONField(default=dict, blank=True)
    test = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)

    tracking_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="processing",)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-generate name if not provided
        if not self.name:
            count = PurchasedTemplate.objects.filter(buyer=self.buyer, template=self.template).count() + 1
            self.name = f"{self.template.name} #{count}"

        if self.svg:
            self.form_fields = parse_svg_to_form_fields(self.svg)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.buyer.username} - {self.template.name} ({'test' if self.test else 'paid'})"
