import os
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings

async def handle_write_signature(args: dict, valid_field_ids: list):
    """
    Generate a signature image (PNG data URL) from a name or style index.
    Args:
        field_id (str): The signature field to update.
        full_name (str, optional): The name to draw.
        style_index (int, optional): 1-9 indicating which preset style to use.
    """
    field_id = args.get("field_id")
    full_name = args.get("full_name")
    style_index = args.get("style_index", 1)

    if field_id not in valid_field_ids:
        return {"events": [], "text": f"Error: '{field_id}' is not a valid field for this template."}

    try:
        # 1. try to generate or load the signature image
        img = None
        
        # If no name is provided, or if specifically asked for a style, try presets first
        if not full_name and 1 <= style_index <= 9:
            preset_path = os.path.join(settings.BASE_DIR, 'api', 'static', 'signatures', f'sign{style_index}.png')
            if os.path.exists(preset_path):
                img = Image.open(preset_path)
            else:
                # Fallback to a name if preset doesn't exist? 
                full_name = full_name or "Signature"

        if full_name:
            # Create a transparent image for the signature
            width, height = 400, 150
            img = Image.new('RGBA', (width, height), (255, 255, 255, 0))
            draw = ImageDraw.Draw(img)
            
            # Load font
            font_path = os.path.join(settings.BASE_DIR, 'api', 'fonts', 'static', 'fonts', 'DancingScript-Regular.ttf')
            
            try:
                # Try to find font size that fits the name
                font_size = 60
                font = ImageFont.truetype(font_path, font_size)
                
                # Center text
                left, top, right, bottom = draw.textbbox((0, 0), full_name, font=font)
                text_width = right - left
                text_height = bottom - top
                
                # Draw the name in dark blue/black (signature-like)
                # Position: centered horizontally, slightly above vertical center
                x = (width - text_width) / 2
                y = (height - text_height) / 2
                draw.text((x, y), full_name, font=font, fill=(0, 0, 128, 255)) # Navy blue signature
                
            except Exception as e:
                # Fallback to default font if custom font fails
                print(f"Font error: {e}")
                draw.text((10, 50), full_name, fill=(0, 0, 0, 255))

        if not img:
            return {"events": [], "text": "Failed to generate signature image."}

        # 2. Convert to base64 data URL
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        data_url = f"data:image/png;base64,{img_str}"

        return {
            "events": [
                {
                    "type": "field_update",
                    "payload": {"id": field_id, "value": data_url}
                }
            ],
            "text": f"Signature for '{full_name or f'Style {style_index}'}' added to {field_id}."
        }

    except Exception as e:
        return {"events": [], "text": f"Signature error: {str(e)}"}
