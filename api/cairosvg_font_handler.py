"""
Utility to prepare SVG for CairoSVG rendering with custom fonts
CairoSVG requires fonts to be installed on the system and uses Fontconfig
"""
import re
from typing import List, Dict
from .models import Font
from .font_installer import ensure_fonts_installed, get_font_family_name_from_file


def prepare_svg_for_cairosvg(svg_content: str, fonts: List[Font]) -> str:
    """
    Prepare SVG for CairoSVG rendering by:
    1. Installing fonts to the system
    2. Replacing font-family names with system font names
    3. Using font-weight attributes instead of separate font families
    
    Args:
        svg_content: SVG content as string
        fonts: List of Font objects to use
        
    Returns:
        Modified SVG content ready for CairoSVG
    """
    if not fonts:
        return svg_content
    
    # Install fonts and get system font names
    font_map = ensure_fonts_installed(fonts)
    
    # Create mapping: original font name -> system font name
    # Also create a reverse map for matching
    name_mapping = {}
    for font in fonts:
        system_name = font_map.get(font.id, font.name)
        # Map both the font name and normalized versions
        name_mapping[font.name] = system_name
        name_mapping[font.name.lower()] = system_name
        name_mapping[font.name.replace(' ', '')] = system_name
        name_mapping[font.name.replace('-', '')] = system_name
        
        # Also try to get from file if available
        if font.font_file:
            file_name = get_font_family_name_from_file(font)
            name_mapping[file_name] = system_name
    
    # Extract all font-family references from SVG
    font_family_pattern = re.compile(r'font-family\s*:\s*([^;,\n]+)', re.IGNORECASE)
    font_family_attr_pattern = re.compile(r'font-family\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
    
    # Find all font-family usages
    used_fonts = set()
    
    # In style blocks
    style_pattern = r'<style[^>]*>(.*?)</style>'
    for style_match in re.finditer(style_pattern, svg_content, re.DOTALL | re.IGNORECASE):
        style_content = style_match.group(1)
        for match in font_family_pattern.finditer(style_content):
            font_name = match.group(1).strip().strip('\'"')
            used_fonts.add(font_name)
    
    # In style attributes
    style_attr_pattern = r'style\s*=\s*["\']([^"\']+)["\']'
    for match in re.finditer(style_attr_pattern, svg_content, re.IGNORECASE):
        style_attr = match.group(1)
        for font_match in font_family_pattern.finditer(style_attr):
            font_name = font_match.group(1).strip().strip('\'"')
            used_fonts.add(font_name)
    
    # In font-family attributes
    for match in font_family_attr_pattern.finditer(svg_content, re.IGNORECASE):
        font_name = match.group(1).strip().strip('\'"')
        used_fonts.add(font_name)
    
    # Replace font-family names with system font names
    result = svg_content
    
    for original_name in used_fonts:
        # Try to find matching system font
        system_name = None
        
        # Direct match
        if original_name in name_mapping:
            system_name = name_mapping[original_name]
        else:
            # Try normalized matching
            normalized_original = re.sub(r'[^a-z0-9]', '', original_name.lower())
            for key, value in name_mapping.items():
                normalized_key = re.sub(r'[^a-z0-9]', '', str(key).lower())
                if normalized_original == normalized_key:
                    system_name = value
                    break
        
        if system_name and system_name != original_name:
            # Replace in CSS
            result = re.sub(
                rf'font-family\s*:\s*["\']?{re.escape(original_name)}["\']?',
                f'font-family: "{system_name}"',
                result,
                flags=re.IGNORECASE
            )
            # Replace in attributes
            result = re.sub(
                rf'font-family\s*=\s*["\']{re.escape(original_name)}["\']',
                f'font-family="{system_name}"',
                result,
                flags=re.IGNORECASE
            )
    
    # Handle font-weight: If font name contains "Bold", "Medium", etc., use font-weight attribute
    # This is based on the research finding that CairoSVG works better with font-weight
    
    # Find text elements with font-family and add font-weight if needed
    text_elements_pattern = r'(<text[^>]*>.*?</text>)'
    
    def add_font_weight(match):
        text_element = match.group(1)
        
        # Check if font-family contains weight indicators
        if re.search(r'font-family\s*[=:]\s*["\']?[^"\']*[Bb]old', text_element, re.IGNORECASE):
            # Add font-weight="700" (bold)
            if 'font-weight' not in text_element:
                text_element = re.sub(
                    r'(<text[^>]*)(>)',
                    r'\1 font-weight="700"\2',
                    text_element
                )
        elif re.search(r'font-family\s*[=:]\s*["\']?[^"\']*[Mm]edium', text_element, re.IGNORECASE):
            # Add font-weight="500" (medium)
            if 'font-weight' not in text_element:
                text_element = re.sub(
                    r'(<text[^>]*)(>)',
                    r'\1 font-weight="500"\2',
                    text_element
                )
        
        return text_element
    
    result = re.sub(text_elements_pattern, add_font_weight, result, flags=re.DOTALL | re.IGNORECASE)
    
    return result

