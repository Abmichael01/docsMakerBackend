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
        
        # Very aggressive scaling based on SVG size - ensure plenty of watermarks
        # Calculate based on pixel density: aim for watermarks every ~150-200 pixels
        if area < 30000:  # ID card size SVGs (< ~173x173)
            watermark_count = max(12, int(area / 2500))  # Very dense: 1 per 2.5k units, minimum 12
        elif area < 80000:  # Very small SVGs (< ~283x283)
            watermark_count = max(18, int(area / 2000))  # Very dense: 1 per 2k units, minimum 18
        elif area < 200000:  # Small SVGs (< ~447x447)
            watermark_count = max(30, int(area / 2500))  # Very dense: 1 per 2.5k units, minimum 30
        elif area < 500000:  # Medium SVGs (< ~707x707)
            watermark_count = max(60, int(area / 3000))  # Very dense: 1 per 3k units, minimum 60
        elif area < 1000000:  # Large SVGs (< ~1000x1000)
            watermark_count = max(100, int(area / 4000))  # Very dense: 1 per 4k units, minimum 100
        elif area < 2000000:  # Very large SVGs (< ~1414x1414)
            watermark_count = max(150, int(area / 5000))  # Very dense: 1 per 5k units, minimum 150
        else:  # Extra large SVGs
            watermark_count = max(200, int(area / 6000))  # Very dense: 1 per 6k units, minimum 200
        
        # Increase cap significantly to allow many watermarks for very large documents
        watermark_count = min(watermark_count, 400)  # Maximum 400 watermarks
        
        # Calculate appropriate font size based on SVG dimensions
        # Scale font size to be proportional to SVG size
        avg_dimension = (width + height) / 2
        font_size = max(12, min(60, int(avg_dimension / 15)))  # Font size between 12-60px
        
        # Estimate text width: "TEST DOCUMENT" is ~13 characters
        # Approximate width: font_size * 0.65 * character_count
        text_width = font_size * 0.65 * 13  # Approximately 8.45 * font_size
        text_height = font_size * 1.2  # Approximate text height (with line height)
        
        # Diagonal angle in degrees (negative for top-left to bottom-right)
        angle_degrees = -45
        angle_radians = abs(angle_degrees) * 3.14159265359 / 180  # Convert to radians
        
        # Step 1: Calculate the bounding box of rotated text to prevent overlap
        # When text is rotated, we need to calculate the space it occupies
        # For a rectangle rotated by angle θ:
        # bounding_width = width * |cos(θ)| + height * |sin(θ)|
        # bounding_height = width * |sin(θ)| + height * |cos(θ)|
        cos_angle = abs(0.70710678118)  # cos(45°) = √2/2
        sin_angle = abs(0.70710678118)  # sin(45°) = √2/2
        
        # Calculate bounding box dimensions of rotated text
        watermark_bbox_width = (text_width * cos_angle) + (text_height * sin_angle)
        watermark_bbox_height = (text_width * sin_angle) + (text_height * cos_angle)
        
        # Add minimal padding to ensure no overlap (very tight spacing at pixel level)
        # Calculate exact pixel spacing needed
        padding_factor = 1.1  # Only 10% spacing (very tight, pixel-level calculation)
        min_spacing_x = watermark_bbox_width * padding_factor
        min_spacing_y = watermark_bbox_height * padding_factor
        
        # At pixel level: ensure we can fit watermarks efficiently
        # If spacing is too tight, we might overlap, so use a minimum safe spacing
        # Minimum safe spacing = bounding box + small buffer (5-10 pixels)
        pixel_buffer = max(5, font_size * 0.1)  # Small buffer in pixels
        min_spacing_x = max(min_spacing_x, watermark_bbox_width + pixel_buffer)
        min_spacing_y = max(min_spacing_y, watermark_bbox_height + pixel_buffer)
        
        # Step 2: Calculate available space for watermarks
        # Smaller left margin to start closer to left border
        left_margin_percent = 0.01  # 1% margin on left (very close to border)
        right_margin_percent = 0.05  # 5% margin on right
        top_margin_percent = 0.05  # 5% margin on top
        bottom_margin_percent = 0.05  # 5% margin on bottom
        
        available_width = width * (1 - left_margin_percent - right_margin_percent)
        available_height = height * (1 - top_margin_percent - bottom_margin_percent)
        
        # Step 3: Calculate optimal grid dimensions based on minimum spacing (pixel-level math)
        # Calculate how many columns and rows can fit without overlap
        # Use floor division to get maximum possible positions
        max_cols = max(1, int(available_width / min_spacing_x))
        max_rows = max(1, int(available_height / min_spacing_y))
        
        # Calculate optimal cols and rows to fit watermark_count
        # Use pixel-level calculation: maximize watermark placement
        aspect_ratio = width / height if height > 0 else 1
        
        # Calculate ideal grid dimensions based on watermark count and available space
        # Try to maximize the number of watermarks we can place
        if aspect_ratio >= 1:
            # Wide or square: prefer more columns
            # Calculate based on available space, not just watermark count
            ideal_cols = min(max_cols, max(1, int((watermark_count * aspect_ratio) ** 0.5)))
            ideal_rows = max(1, (watermark_count + ideal_cols - 1) // ideal_cols)
            
            # If we can fit more, increase columns
            while ideal_cols < max_cols and ideal_cols * ideal_rows < watermark_count:
                ideal_cols += 1
                ideal_rows = max(1, (watermark_count + ideal_cols - 1) // ideal_cols)
            
            cols = min(ideal_cols, max_cols)
            rows = min(ideal_rows, max_rows)
        else:
            # Tall: prefer more rows
            ideal_rows = min(max_rows, max(1, int((watermark_count / aspect_ratio) ** 0.5)))
            ideal_cols = max(1, (watermark_count + ideal_rows - 1) // ideal_rows)
            
            # If we can fit more, increase rows
            while ideal_rows < max_rows and ideal_cols * ideal_rows < watermark_count:
                ideal_rows += 1
                ideal_cols = max(1, (watermark_count + ideal_rows - 1) // ideal_rows)
            
            rows = min(ideal_rows, max_rows)
            cols = min(ideal_cols, max_cols)
        
        # Final adjustment: ensure we use all available space efficiently
        # Recalculate watermark_count based on actual grid size
        actual_watermark_count = min(watermark_count, cols * rows)
        
        # Step 4: Calculate actual spacing based on available space and grid size
        # Calculate spacing to evenly distribute watermarks without overlap
        if cols > 1:
            # Space needed for cols watermarks: (cols - 1) * min_spacing_x
            total_needed_width = (cols - 1) * min_spacing_x
            if total_needed_width <= available_width:
                # Use minimum spacing
                actual_spacing_x = min_spacing_x
            else:
                # Scale down spacing to fit
                actual_spacing_x = available_width / (cols - 1)
        else:
            actual_spacing_x = 0
        
        if rows > 1:
            # Space needed for rows watermarks: (rows - 1) * min_spacing_y
            total_needed_height = (rows - 1) * min_spacing_y
            if total_needed_height <= available_height:
                # Use minimum spacing
                actual_spacing_y = min_spacing_y
            else:
                # Scale down spacing to fit
                actual_spacing_y = available_height / (rows - 1)
        else:
            actual_spacing_y = 0
        
        # Step 5: Calculate x positions for each column (same x for all items in a column)
        # Start closer to left border
        x_positions = []
        if cols == 1:
            x_positions = [width * left_margin_percent + watermark_bbox_width / 2]  # Start near left
        else:
            # Calculate total width used by grid
            total_grid_width = (cols - 1) * actual_spacing_x
            # Start from left margin instead of centering
            start_x = width * left_margin_percent + watermark_bbox_width / 2
            for col in range(cols):
                x_pos = start_x + (col * actual_spacing_x)
                x_positions.append(x_pos)
        
        # Step 6: Calculate y positions for each row (same y for all items in a row)
        # Center the grid in available space
        y_positions = []
        if rows == 1:
            y_positions = [height / 2]  # Center single row
        else:
            # Calculate total height used by grid
            total_grid_height = (rows - 1) * actual_spacing_y
            start_y = (height - total_grid_height) / 2  # Center the grid
            for row in range(rows):
                y_pos = start_y + (row * actual_spacing_y)
                y_positions.append(y_pos)
        
        # Step 7: Assign watermarks to grid positions one by one
        # Use the actual watermark count based on grid capacity
        final_watermark_count = min(watermark_count, cols * rows)
        watermarks = []
        watermark_index = 0
        
        for row in range(rows):
            for col in range(cols):
                if watermark_index >= final_watermark_count:
                    break
                
                # Get base x and y from calculated positions
                base_x = x_positions[col]  # Same x for all items in this column
                base_y = y_positions[row]  # Same y for all items in this row
                
                # Step 7: Apply diagonal offset to create slanted pattern
                # Shift each row horizontally to create diagonal effect
                # But ensure we don't cause overlap
                if cols > 1 and rows > 1:
                    # Calculate safe diagonal shift (don't exceed half the spacing)
                    # This ensures rotated watermarks don't overlap
                    safe_shift = actual_spacing_x * 0.3  # 30% shift is safe
                    # Apply shift proportional to row position
                    x = base_x + (safe_shift * row / max(1, rows - 1))
                else:
                    x = base_x
                
                y = base_y
                
                # Ensure watermarks stay within bounds (account for rotated bounding box)
                margin_x = watermark_bbox_width / 2
                margin_y = watermark_bbox_height / 2
                if x < margin_x or x > width - margin_x or y < margin_y or y > height - margin_y:
                    continue
                
                # Wrap in transform group with rotation
                watermark = (
                    f'<g transform="rotate({angle_degrees}, {x}, {y})">'
                    f'<text x="{x}" y="{y}" fill="black" font-size="{font_size}" pointer-events="none">'
                    f'TEST DOCUMENT</text></g>'
                )
                watermarks.append(watermark)
                watermark_index += 1
            
            if watermark_index >= final_watermark_count:
                break
        
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

        # Regex to match the watermark text elements
        # This matches <text ...>TEST DOCUMENT</text> with pointer-events="none"
        # Supports both old rotated format and new organized slanted format
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

