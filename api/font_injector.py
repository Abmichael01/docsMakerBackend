"""
Utility to inject @font-face declarations into SVG content
"""
import base64
import os
import re
import tempfile
from typing import List, Optional, Tuple
from django.conf import settings
from .models import Font


def _build_font_face(font_family: str, font_url: str, font_format: str) -> str:
    return f'''@font-face {{
  font-family: "{font_family}";
  src: url("{font_url}") format("{font_format}");
}}'''


def _normalize_font_key(name: Optional[str]) -> str:
    if not name:
        return ""
    return re.sub(r'[^a-z0-9]', '', name.lower())


def _extract_font_aliases(svg_content: str) -> dict:
    """
    Extract all font-family names actually used in the SVG.
    Returns a map: normalized_key -> exact_font_family_name_as_used_in_svg
    """
    alias_map = {}
    
    # Pattern to find font-family in CSS (inside <style> blocks)
    font_family_css_pattern = re.compile(r'font-family\s*:\s*([^;,\n]+)', re.IGNORECASE)
    
    # Pattern to find font-family in style attributes
    style_attr_pattern = re.compile(r'style\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
    
    # Pattern to find font-family as XML attribute
    font_family_attr_pattern = re.compile(r'font-family\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
    
    def add_alias(value: str):
        """Add font family to alias map with exact name preservation"""
        # Take first font-family (before comma, which indicates fallbacks)
        first_family = value.split(',')[0].strip().strip('\'"')
        if not first_family:
            return
        
        # Normalize for matching, but store the EXACT original
        key = _normalize_font_key(first_family)
        if key:
            # Store the exact name as it appears in SVG (preserves quotes, spacing, case)
            alias_map[key] = first_family
    
    # Extract from <style> blocks
    style_pattern = r'<style[^>]*>(.*?)</style>'
    for style_block in re.findall(style_pattern, svg_content, re.DOTALL | re.IGNORECASE):
        for match in font_family_css_pattern.findall(style_block):
            add_alias(match)
    
    # Extract from style attributes (inline styles)
    for style_attr in style_attr_pattern.findall(svg_content):
        for match in font_family_css_pattern.findall(style_attr):
            add_alias(match)
    
    # Extract from font-family XML attributes 
    for match in font_family_attr_pattern.findall(svg_content):
        add_alias(match)
    
    return alias_map

 
def _get_font_candidates(font: Font) -> List[str]:
    candidates = []
    if getattr(font, "name", None):
        candidates.append(font.name)
    if font.font_file:
        filename = os.path.basename(font.font_file.name)
        stem, _ = os.path.splitext(filename)
        if stem:
            candidates.append(stem)
    return candidates


def inject_fonts_into_svg(svg_content: str, fonts: List[Font], base_url: Optional[str] = None, embed_base64: bool = False) -> str:
    """
    Inject @font-face declarations into SVG content
    
    Args:
        svg_content: The SVG content as a string
        fonts: List of Font objects to inject
        base_url: Base URL for font files (for frontend use)
        embed_base64: If True, embed fonts as base64 (for backend PDF/PNG generation)
    
    Returns:
        SVG content with @font-face declarations injected
    """
    if not fonts:
        return svg_content
    
    # Find or create <defs> section (case insensitive)
    defs_pattern = re.compile(r'(<defs[^>]*>)(.*?)(</defs>)', re.IGNORECASE | re.DOTALL)
    defs_match = defs_pattern.search(svg_content)
    
    alias_map = _extract_font_aliases(svg_content)
    
    # Generate @font-face declarations
    font_faces: List[Tuple[str, str]] = []
    for font in fonts:
        font_family = font.name
        font_format = font.get_font_format()
        font_url: Optional[str] = None
        
        if embed_base64:
            # Embed font as base64 for backend rendering
            try:
                if not font.font_file:
                    continue
                font.font_file.open("rb")
                try:
                    font_data = font.font_file.read()
                finally:
                    font.font_file.close()
                font_base64 = base64.b64encode(font_data).decode('utf-8')
                # Use proper MIME types for different font formats
                mime_type_map = {
                    'truetype': 'application/font-truetype',
                    'opentype': 'application/font-opentype',
                    'woff': 'application/font-woff',
                    'woff2': 'application/font-woff2',
                }
                mime_type = mime_type_map.get(font_format, 'application/font-truetype')
                font_url = f"data:{mime_type};base64,{font_base64}"
            except Exception as e:
                print(f"Error reading font file {font.name}: {e}")
                continue
        else:
            # Use URL for frontend rendering
            if not font.font_file:
                continue
            font_url = font.font_file.url
            if base_url and font_url and not font_url.startswith("http"):
                font_url = f"{base_url}{font_url}"
        
        if not font_url:
            continue
        
        # Try to match font to what's actually used in SVG
        candidates = _get_font_candidates(font)
        css_family = None
        
        # First, try to find exact match in alias_map (what SVG actually uses)
        for candidate in candidates:
            key = _normalize_font_key(candidate)
            if key and key in alias_map:
                # Use the EXACT font-family name as it appears in the SVG
                css_family = alias_map[key]
                break
        
        # If no match found, check if any alias matches our font name (reverse lookup)
        if not css_family:
            font_key = _normalize_font_key(font.name)
            if font_key and font_key in alias_map:
                css_family = alias_map[font_key]
        
        # Fallback: use font name, but this might not match SVG exactly
        if not css_family:
            css_family = font.name or (candidates[0] if candidates else "CustomFont")
            # Log warning if we couldn't match
            if alias_map:
                print(f"Warning: Font '{font.name}' not found in SVG. SVG uses: {list(alias_map.values())}")
        
        font_faces.append((css_family, _build_font_face(css_family, font_url, font_format)))
    
    if not font_faces:
        return svg_content
    
    # Deduplicate font-faces by family name (normalized) to avoid duplicates
    # Map: normalized_family_key -> (css_family, font_face_css)
    unique_font_map = {}
    for css_family, font_face in font_faces:
        family_key = _normalize_font_key(css_family)
        if family_key not in unique_font_map:
            unique_font_map[family_key] = (css_family, font_face)
    
    if not unique_font_map:
        return svg_content
    
    # Extract unique font-face CSS strings
    unique_font_faces = [font_face for _, font_face in unique_font_map.values()]
    
    # Combine all font-face declarations
    font_faces_css = '\n'.join(unique_font_faces)
    
    # Create style block with font-face declarations
    style_block = f'<style type="text/css"><![CDATA[\n{font_faces_css}\n]]></style>'
    
    if defs_match:
        defs_start, defs_content, defs_end = defs_match.groups()
        defs_full = defs_match.group(0)
        
        style_pattern = re.compile(r'(<style[^>]*>)(<!\[CDATA\[)?(.*?)(\]\]>)?(</style>)', re.IGNORECASE | re.DOTALL)
        style_match = style_pattern.search(defs_content)
        
        if style_match:
            style_full = style_match.group(0)
            style_open, cdata_open, existing_style, cdata_close, style_close = style_match.groups()
            
            # Extract existing font-families from @font-face declarations ONLY (not from regular CSS)
            # This prevents skipping fonts that are used in CSS but don't have @font-face yet
            existing_families = set()
            # Match @font-face blocks first, then extract font-family from within them
            # Use balanced brace matching to handle nested braces in url() values
            font_face_block_pattern = re.compile(r'@font-face\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', re.IGNORECASE | re.DOTALL)
            font_family_in_fontface_pattern = re.compile(r'font-family\s*:\s*["\']([^"\']+)["\']', re.IGNORECASE)
            
            for font_face_block in font_face_block_pattern.findall(existing_style):
                for match in font_family_in_fontface_pattern.findall(font_face_block):
                    existing_families.add(_normalize_font_key(match))
            
            # Only add font-faces that don't already exist (by normalized name)
            missing_font_faces = []
            for family_key, (css_family, font_face) in unique_font_map.items():
                # Check if this font-family already has a @font-face declaration (not just CSS usage)
                if family_key not in existing_families:
                    missing_font_faces.append(font_face)
            
            if missing_font_faces:
                new_style_content = existing_style + '\n' + '\n'.join(missing_font_faces)
                cdata_open = cdata_open or ''
                cdata_close = cdata_close or ''
                new_style_block = f'{style_open}{cdata_open}{new_style_content}{cdata_close}{style_close}'
                new_defs_content = defs_content.replace(style_full, new_style_block, 1)
                new_defs_full = defs_full.replace(defs_content, new_defs_content, 1)
                svg_content = svg_content.replace(defs_full, new_defs_full, 1)
        else:
            # No style block yet, prepend a new one while preserving defs wrapper
            new_defs_content = style_block + '\n' + defs_content
            new_defs_full = defs_full.replace(defs_content, new_defs_content, 1)
            svg_content = svg_content.replace(defs_full, new_defs_full, 1)
    else:
        # Create new <defs> section
        # Find the opening <svg> tag (case insensitive)
        svg_pattern = re.compile(r'(<svg[^>]*>)', re.IGNORECASE)
        svg_match = svg_pattern.search(svg_content)
        if svg_match:
            svg_content = svg_content.replace(svg_match.group(0), svg_match.group(0) + f'\n<defs>\n{style_block}\n</defs>')
    
    return svg_content

