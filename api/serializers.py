# templates/serializers.py
from rest_framework import serializers
from .models import Template, PurchasedTemplate
import random
import re

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
        
        # Remove form_fields on list view
        if view and view.action == 'list':
            representation.pop('form_fields', None)
        
        # Add watermark to SVG if it's a test template
        if instance.test and 'svg' in representation:
            representation['svg'] = self.add_watermark(representation['svg'])
        
        return representation
    

    def add_watermark(self, svg_content):
        """Add simple random watermarks to SVG"""
        if not svg_content or '</svg>' not in svg_content:
            return svg_content
        
        # Get SVG dimensions
        width, height = self.get_svg_size(svg_content)
        
        # Calculate number of watermarks based on area
        area = width * height
        watermark_count = int(area / 5000)  # 1 watermark per 5000 square units
        watermark_count = max(10, min(watermark_count, 100))  # Between 10-100 watermarks
        
        # Generate watermarks
        watermarks = []
        for _ in range(watermark_count):
            x = random.randint(0, int(width))
            y = random.randint(0, int(height))
            angle = random.randint(-45, 45)
            
            # watermark = f'<text x="{x}" y="{y}" transform="rotate({angle}, {x}, {y})" fill="black" font-size="40" pointer-events="none">TEST TEMPLATE</text>'
            watermark = (
                f'<g transform="rotate({angle}, {x}, {y})">'
                f'<text x="{x}" y="{y}" fill="black" font-size="40" pointer-events="none">'
                f'TEST DOCUMENT</text></g>'
            )
            watermarks.append(watermark)
        
        # Insert before </svg>
        watermark_text = '\n'.join(watermarks)
        return svg_content.replace('</svg>', f'{watermark_text}\n</svg>')

    def get_svg_size(self, svg_content):
        """Get SVG width and height"""
        # Default size 
        width, height = 400, 300
        
        # Try viewBox first
        viewbox = re.search(r'viewBox=["\']([^"\']+)["\']', svg_content)
        if viewbox:
            values = viewbox.group(1).split()
            if len(values) >= 4:
                width = float(values[2])
                height = float(values[3])
                return width, height
        
        # Try width/height attributes
        width_match = re.search(r'width=["\']([^"\'px]+)', svg_content)
        height_match = re.search(r'height=["\']([^"\'px]+)', svg_content)
        
        if width_match:
            width = float(width_match.group(1))
        if height_match:
            height = float(height_match.group(1))
        
        return width, height

