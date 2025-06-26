# templates/serializers.py
from rest_framework import serializers
from .models import Template, PurchasedTemplate


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Template
        fields = '__all__'
        
    def to_representation(self, instance):
        # Get the base representation
        representation = super().to_representation(instance)
        request = self.context.get('request')
        view = self.context.get('view')
        if view and view.action == 'list':
            representation.pop('form_fields', None)  # Remove it on list
        return representation


class PurchasedTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchasedTemplate
        fields = '__all__'
        read_only_fields = ('buyer',)
    
    def to_representation(self, instance):
        # Get the base representation
        representation = super().to_representation(instance)
        request = self.context.get('request')
        view = self.context.get('view')
        if view and view.action == 'list':
            representation.pop('form_fields', None)  # Remove it on list
        return representation
