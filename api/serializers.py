# templates/serializers.py
from rest_framework import serializers

from api.watermark import WaterMark
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
        
    def charge_if_test_false(self, instance, validated_data, is_update=False):
        old_test = instance.test if is_update else True  # Assume default True for new records
        new_test = validated_data.get("test", old_test)

        # Charge only if test changes from True to False
        if old_test is True and new_test is False:
            user = instance.buyer

            if not hasattr(user, "wallet"):
                raise serializers.ValidationError("User does not have a wallet.")

            charge_amount = 5
            if user.wallet.balance < charge_amount:
                raise serializers.ValidationError("Insufficient funds to remove watermark.")

            user.wallet.debit(charge_amount, description="Document purchase")
            print("Charging ₦5 for watermark removal...")

    def update(self, instance, validated_data):
        self.charge_if_test_false(instance, validated_data, is_update=True)
        return super().update(instance, validated_data)

    def create(self, validated_data):
        # Create a temporary instance to simulate access to `buyer` and `test`
        temp_instance = self.Meta.model(**validated_data)
        self.charge_if_test_false(temp_instance, validated_data, is_update=False)
        return super().create(validated_data)

    def to_representation(self, instance):
        # Get the base representation
        representation = super().to_representation(instance)
        request = self.context.get('request')
        view = self.context.get('view')
        
        # Remove form_fields on list view
        if view and view.action == 'list':
            representation.pop('form_fields', None)
        
        # Add watermark to SVG if it's a test template
        if instance.test and 'svg' in representation:
            representation['svg'] = WaterMark().add_watermark(representation['svg'])
        
        return representation
    

    