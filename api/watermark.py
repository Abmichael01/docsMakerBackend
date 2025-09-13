import random
import re

class WaterMark():
    def add_watermark(self, svg_content):
        """Add simple random watermarks to SVG"""
        if not svg_content or '</svg>' not in svg_content:
            return svg_content
        
        # Get SVG dimensions
        width, height = self.get_svg_size(svg_content)
        
        # Calculate number of watermarks based on area with better scaling
        area = width * height
        
        # More intelligent scaling based on SVG size
        if area < 30000:  # ID card size SVGs (< ~173x173)
            watermark_count = max(1, int(area / 20000))  # 1 watermark per 20k units, minimum 1
        elif area < 80000:  # Very small SVGs (< ~283x283)
            watermark_count = max(1, int(area / 15000))  # 1 watermark per 15k units, minimum 1
        elif area < 200000:  # Small SVGs (< ~447x447)
            watermark_count = max(2, int(area / 20000))  # 1 watermark per 20k units, minimum 2
        elif area < 500000:  # Medium SVGs (< ~707x707)
            watermark_count = max(3, int(area / 25000))  # 1 watermark per 25k units, minimum 3
        else:  # Large SVGs
            watermark_count = max(5, int(area / 30000))  # 1 watermark per 30k units, minimum 5
        
        # Cap maximum watermarks to prevent overcrowding
        watermark_count = min(watermark_count, 50)  # Maximum 50 watermarks
        
        # Calculate appropriate font size based on SVG dimensions
        # Scale font size to be proportional to SVG size
        avg_dimension = (width + height) / 2
        font_size = max(12, min(60, int(avg_dimension / 15)))  # Font size between 12-60px
        
        # Generate watermarks
        watermarks = []
        for _ in range(watermark_count):
            x = random.randint(0, int(width))
            y = random.randint(0, int(height))
            angle = random.randint(-45, 45)
            
            watermark = (
                f'<g transform="rotate({angle}, {x}, {y})">'
                f'<text x="{x}" y="{y}" fill="black" font-size="{font_size}" pointer-events="none">'
                f'TEST DOCUMENT</text></g>'
            )
            watermarks.append(watermark)
        
        # Insert before </svg>
        watermark_text = '\n'.join(watermarks)
        return svg_content.replace('</svg>', f'{watermark_text}\n</svg>')

    def remove_watermark(self, svg_content):
        """
        Remove all watermark elements added by add_watermark.
        Specifically removes <g> elements containing <text>TEST DOCUMENT</text> with the expected attributes.
        """
        if not svg_content or '</svg>' not in svg_content:
            return svg_content

        # Regex to match the watermark <g>...</g> blocks
        # This matches <g ...><text ...>TEST DOCUMENT</text></g> possibly with newlines and spaces
        watermark_pattern = re.compile(
            r'<g\s+transform="rotate\([^)]+\)">\s*'
            r'<text\s+[^>]*pointer-events="none"[^>]*>'
            r'TEST DOCUMENT</text>\s*</g>',
            re.IGNORECASE | re.DOTALL
        )
        cleaned_svg = re.sub(watermark_pattern, '', svg_content)
        return cleaned_svg

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

