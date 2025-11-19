"""
Utility to render SVG to PDF/PNG using Playwright (headless browser)
This provides full @font-face support with data URIs

Creates browser instances directly (no pooling) to avoid async context issues.
"""
import re
from typing import Optional
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page


# Removed singleton pattern - create browser instances directly to avoid async context issues


def render_svg_with_playwright(svg_content: str, output_type: str = "png", width: Optional[int] = None, height: Optional[int] = None) -> bytes:
    """
    Render SVG to PDF or PNG using Playwright
    
    Args:
        svg_content: SVG content as string
        output_type: "pdf" or "png"
        width: Optional width for PNG (defaults to SVG viewBox or 1200)
        height: Optional height for PNG (defaults to SVG viewBox or 1600)
    
    Returns:
        Bytes of the rendered output
    """
    print("  [Playwright] === Rendering started ===")
    print(f"  [Playwright] Output type: {output_type}")
    print(f"  [Playwright] SVG content length: {len(svg_content)}")
    
    playwright = None
    browser = None
    context = None
    page = None
    
    try:
        # Create browser instance directly (no singleton/pooling to avoid async issues)
        try:
            print("  [Playwright] Initializing Playwright...")
            playwright = sync_playwright().start()
            print("  [Playwright] Playwright started, launching browser...")
            browser = playwright.chromium.launch(
                headless=True,
                args=['--disable-dev-shm-usage', '--disable-gpu', '--no-sandbox']
            )
            print("  [Playwright] Browser launched successfully")
            
            print("  [Playwright] Creating browser context...")
            context = browser.new_context()
            print("  [Playwright] Browser context created, creating new page...")
            page = context.new_page()
            print("  [Playwright] Page created successfully")
        except Exception as e:
            import traceback
            error_msg = f"Failed to initialize Playwright: {str(e)}\n{traceback.format_exc()}"
            print(f"  [Playwright] ERROR: {error_msg}")
            raise Exception(error_msg)
        
        # Extract dimensions from SVG if not provided
        print("  [Playwright] Extracting SVG dimensions...")
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
        
        print(f"  [Playwright] Using dimensions: {width}x{height}")
        
        # Set viewport to match SVG dimensions
        print("  [Playwright] Setting viewport size...")
        page.set_viewport_size({"width": width, "height": height})
        print("  [Playwright] Viewport size set")
        
        # Create HTML with SVG embedded
        print("  [Playwright] Creating HTML wrapper...")
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        html, body {{
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
        
        # Load the HTML - use "load" for PDF to ensure everything is ready
        wait_until = "load" if output_type.lower() == "pdf" else "domcontentloaded"
        print(f"  [Playwright] Loading HTML content into page (wait_until={wait_until})...")
        page.set_content(html_content, wait_until=wait_until)
        print("  [Playwright] HTML content loaded")
        
        # Wait for fonts to load (fonts in @font-face need time)
        wait_time = 2000 if output_type.lower() == "pdf" else 1000
        print(f"  [Playwright] Waiting for fonts to load ({wait_time}ms)...")
        page.wait_for_timeout(wait_time)
        print("  [Playwright] Font loading wait complete")
        
        if output_type.lower() == "pdf":
            # Generate PDF
            print("  [Playwright] Generating PDF...")
            try:
                pdf_bytes = page.pdf(
                    width=f"{width}px",
                    height=f"{height}px",
                    print_background=True,
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                    prefer_css_page_size=True
                )
                if not pdf_bytes or len(pdf_bytes) == 0:
                    raise Exception("PDF generation returned empty bytes")
                print(f"  [Playwright] SUCCESS: PDF generated. Size: {len(pdf_bytes)} bytes")
                return pdf_bytes
            except Exception as e:
                print(f"  [Playwright] ERROR: PDF generation failed: {str(e)}")
                import traceback
                print(traceback.format_exc())
                raise
        else:
            # Generate PNG - use page screenshot instead of element screenshot to avoid font loading timeout
            print("  [Playwright] Generating PNG...")
            # Use page screenshot with timeout disabled to avoid font loading issues
            try:
                screenshot_bytes = page.screenshot(
                    type="png",
                    clip={"x": 0, "y": 0, "width": width, "height": height},
                    timeout=60000  # Increase timeout to 60 seconds
                )
            except Exception as e:
                print(f"  [Playwright] WARNING: Page screenshot failed, trying element screenshot: {str(e)}")
                # Fallback to element screenshot
                svg_element = page.query_selector("svg")
                if svg_element:
                    print("  [Playwright] Taking SVG element screenshot with extended timeout...")
                    screenshot_bytes = svg_element.screenshot(type="png", timeout=60000)
                else:
                    raise Exception("SVG element not found and page screenshot failed")
            print(f"  [Playwright] SUCCESS: PNG generated. Size: {len(screenshot_bytes)} bytes")
            return screenshot_bytes
            
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        error_msg = f"Playwright rendering failed: {str(e)}\n{error_traceback}"
        print("  [Playwright] " + "=" * 50)
        print("  [Playwright] ERROR: RENDERING FAILED")
        print(f"  [Playwright] Error message: {str(e)}")
        print(f"  [Playwright] Error type: {type(e).__name__}")
        print("  [Playwright] Full traceback:")
        print(error_traceback)
        print("  [Playwright] " + "=" * 50)
        raise Exception(error_msg)
    finally:
        # Clean up resources
        print("  [Playwright] Cleaning up...")
        if page:
            try:
                print("  [Playwright] Closing page...")
                page.close()
                print("  [Playwright] Page closed")
            except Exception as e:
                print(f"  [Playwright] WARNING: Error closing page: {str(e)}")
        
        if context:
            try:
                print("  [Playwright] Closing context...")
                context.close()
                print("  [Playwright] Context closed")
            except Exception as e:
                print(f"  [Playwright] WARNING: Error closing context: {str(e)}")
        
        if browser:
            try:
                print("  [Playwright] Closing browser...")
                browser.close()
                print("  [Playwright] Browser closed")
            except Exception as e:
                print(f"  [Playwright] WARNING: Error closing browser: {str(e)}")
        
        if playwright:
            try:
                print("  [Playwright] Stopping Playwright...")
                playwright.stop()
                print("  [Playwright] Playwright stopped")
            except Exception as e:
                print(f"  [Playwright] WARNING: Error stopping Playwright: {str(e)}")
        
        print("  [Playwright] === Rendering completed ===")

