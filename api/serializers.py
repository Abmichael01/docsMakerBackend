# templates/serializers.py
from rest_framework import serializers
from .models import Template, PurchasedTemplate


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Template
        fields = '__all__'


class PurchasedTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchasedTemplate
        fields = '__all__'
        read_only_fields = ('buyer',)
