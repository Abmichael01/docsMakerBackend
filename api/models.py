# models.py
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.postgres.fields import JSONField  # Use `models.JSONField` if Django 3.1+
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from .svg_parser import parse_svg_to_form_fields
# SVG minification removed - SVGs from Photoshop are already optimized and minification can break designs

User = get_user_model()


class Tool(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Tools"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Template(models.Model):
    TEMPLATE_TYPE_CHOICES = [
        ('tool', 'Tool'),
        ('design', 'Design'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    svg = models.TextField()
    banner = models.ImageField(upload_to='template_banners/', blank=True, null=True, help_text="Banner image for the template")
    form_fields = models.JSONField(default=dict, blank=True)
    type = models.CharField(max_length=20, choices=TEMPLATE_TYPE_CHOICES)
    tool = models.ForeignKey(Tool, on_delete=models.SET_NULL, null=True, blank=True, related_name='templates')
    created_at = models.DateTimeField(auto_now_add=True)
    hot = models.BooleanField(default=False)
    

    def save(self, *args, **kwargs):
        if self.svg:
            # Parse SVG to generate form fields
            # SVG is kept as-is (no minification) to preserve Photoshop-exported designs
            self.form_fields = parse_svg_to_form_fields(self.svg)
        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=['type']),
            models.Index(fields=['hot']),
            models.Index(fields=['created_at']),
            models.Index(fields=['tool']),
        ]

    def get_purchased_count(self):
        """Get the number of purchased templates for this template"""
        return self.purchases.count()
    
    def has_purchases(self):
        """Check if this template has any purchased templates"""
        return self.purchases.exists()

    def __str__(self):
        return self.name


class PurchasedTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="purchased_templates")
    template = models.ForeignKey("Template", on_delete=models.SET_NULL, null=True, blank=True, related_name="purchases")
    
    name = models.CharField(max_length=255, blank=True)

    svg = models.TextField()
    form_fields = models.JSONField(default=dict, blank=True)
    test = models.BooleanField(default=True)

    tracking_id = models.CharField(max_length=100, blank=True, null=True, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-generate name if not provided
        if not self.name:
            if self.template:
                count = PurchasedTemplate.objects.filter(buyer=self.buyer, template=self.template).count() + 1
                self.name = f"{self.template.name} #{count}"
            else:
                # Handle orphaned purchased templates
                count = PurchasedTemplate.objects.filter(buyer=self.buyer, template__isnull=True).count() + 1
                self.name = f"Orphaned Template #{count}"

        if self.svg:
            # Parse SVG to generate form fields
            # SVG is kept as-is (no minification) to preserve Photoshop-exported designs
            self.form_fields = parse_svg_to_form_fields(self.svg)

        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=['buyer']),
            models.Index(fields=['template']),
            models.Index(fields=['tracking_id']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        template_name = self.template.name if self.template else "Orphaned Template"
        return f"{self.buyer.username} - {template_name} ({'test' if self.test else 'paid'})"


class Tutorial(models.Model):
    template = models.OneToOneField(Template, on_delete=models.CASCADE, related_name='tutorial')
    url = models.URLField(help_text="Tutorial video URL")
    title = models.CharField(max_length=255, blank=True, help_text="Optional tutorial title")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.template.name} - Tutorial"
