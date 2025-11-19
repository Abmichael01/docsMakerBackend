"""
Utility to render SVG to PDF using WeasyPrint (fast, no browser needed)
WeasyPrint supports @font-face with data URIs and is much faster than Playwright
Note: WeasyPrint only supports PDF output, not PNG
"""
import re
from typing import Optional


def render_svg_with_weasyprint(svg_content: str, width: Optional[int] = None, height: Optional[int] = None) -> bytes:
    """
    Render SVG to PDF using WeasyPrint
    
    Args:
        svg_content: SVG content as string
        width: Optional width (defaults to SVG viewBox or 1200)
        height: Optional height (defaults to SVG viewBox or 1600)
    
    Returns:
        Bytes of the rendered PDF
    """
    try:
        from weasyprint import HTML, CSS
        from weasyprint.text.fonts import FontConfiguration
    except ImportError:
        raise Exception("WeasyPrint is not installed. Install with: pip install weasyprint")
    
    try:
        # Extract dimensions from SVG if not provided
        viewbox_match = re.search(r'viewBox=["\']([^"\']+)["\']', svg_content, re.IGNORECASE)
        svg_width_match = re.search(r'width=["\']([^"\']+)["\']', svg_content, re.IGNORECASE)
        svg_height_match = re.search(r'height=["\']([^"\']+)["\']', svg_content, re.IGNORECASE)
        
        if not width or not height:
            if viewbox_match:
                try:
                    viewbox_parts = viewbox_match.group(1).strip().split()
                    if len(viewbox_parts) >= 4:
                        width = width or int(float(viewbox_parts[2]))
                        height = height or int(float(viewbox_parts[3]))
                except (ValueError, IndexError):
                    pass
            
            if (not width or not height) and svg_width_match and svg_height_match:
                try:
                    width_str = re.sub(r'[^\d.]', '', svg_width_match.group(1))
                    height_str = re.sub(r'[^\d.]', '', svg_height_match.group(1))
                    if width_str:
                        width = width or int(float(width_str))
                    if height_str:
                        height = height or int(float(height_str))
                except (ValueError, AttributeError):
                    pass
        
        # Default dimensions if still not set
        width = width or 1200
        height = height or 1600
        
        # Ensure minimum size
        width = max(width, 100)
        height = max(height, 100)
        
        # Convert pixels to mm for WeasyPrint (1 inch = 25.4mm, 1 inch = 96px)
        width_mm = (width / 96) * 25.4
        height_mm = (height / 96) * 25.4
        
        # Create HTML wrapper for SVG
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {{
            size: {width_mm}mm {height_mm}mm;
            margin: 0;
        }}
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            margin: 0;
            padding: 0;
            width: {width}px;
            height: {height}px;
            overflow: hidden;
        }}
        svg {{
            width: {width}px;
            height: {height}px;
            display: block;
        }}
    </style>
</head>
<body>
    {svg_content}
</body>
</html>"""
        
        # Render to PDF using WeasyPrint
        # WeasyPrint supports @font-face with data URIs natively
        try:
            html = HTML(string=html_content, base_url=None)
            pdf_bytes = html.write_pdf()
            
            if not pdf_bytes or len(pdf_bytes) == 0:
                raise Exception("WeasyPrint returned empty PDF")
            
            return pdf_bytes
        except Exception as e:
            # If WeasyPrint fails, provide more context
            raise Exception(f"WeasyPrint PDF generation failed: {str(e)}")
        
    except Exception as e:
        import traceback
        error_msg = f"WeasyPrint rendering failed: {str(e)}\n{traceback.format_exc()}"
        raise Exception(error_msg)

