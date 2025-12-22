# templates/views.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from .models import Template, PurchasedTemplate, Tool, Tutorial, Font
from .serializers import *
from .permissions import IsAdminOrReadOnly, IsOwnerOrAdmin, IsAdminOnly
from rest_framework.permissions import SAFE_METHODS
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from .font_injector import inject_fonts_into_svg
from .watermark import WaterMark
from .cache_utils import (
    cache_template_list,
    cache_template_detail,
    cache_template_svg,
    invalidate_template_cache
)
import cairosvg

# Try to import Playwright renderer (optional - falls back to CairoSVG if not available)
try:
    from .playwright_renderer import render_svg_with_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    render_svg_with_playwright = None

# Try to import WeasyPrint renderer (faster alternative for PDF with fonts)
try:
    from .weasyprint_renderer import render_svg_with_weasyprint
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    render_svg_with_weasyprint = None


class TemplatePagination(PageNumberPagination):
    """Pagination for Template list views"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class TemplateViewSet(viewsets.ModelViewSet):
    queryset = Template.objects.all().order_by('-created_at')
    serializer_class = TemplateSerializer
    permission_classes = [IsAdminOrReadOnly]
    # No pagination for user-facing template listings
    pagination_class = None
    # authentication_classes = []
    
    def get_authenticators(self):
        if self.request.method in SAFE_METHODS:
            return []  # No authentication for GET/HEAD/OPTIONS
        return super().get_authenticators()
    
    def get_queryset(self):
        queryset = Template.objects.select_related('tool', 'tutorial').prefetch_related('fonts')
        hot_param = self.request.query_params.get("hot")
        tool_param = self.request.query_params.get("tool")

        if hot_param is not None:
            # Convert string to boolean
            if hot_param.lower() == "true":
                queryset = queryset.filter(hot=True)
            elif hot_param.lower() == "false":
                queryset = queryset.filter(hot=False)
        
        if tool_param:
            queryset = queryset.filter(tool__id=tool_param)
        
        # For list views, defer large text fields to improve performance
        if self.action == 'list':
            queryset = queryset.defer('svg', 'form_fields')
        # For detail views, defer SVG to load it separately for better UX
        elif self.action == 'retrieve':
            queryset = queryset.defer('svg')
        
        queryset = queryset.order_by('-created_at')
        return queryset
    
    @cache_template_list(timeout=300)
    def list(self, request, *args, **kwargs):
        """Override list method"""
        return super().list(request, *args, **kwargs)
    
    @cache_template_detail(timeout=600)
    def retrieve(self, request, *args, **kwargs):
        """Override retrieve method to add caching"""
        return super().retrieve(request, *args, **kwargs)
    
    def create(self, request, *args, **kwargs):
        """Override create to invalidate cache"""
        response = super().create(request, *args, **kwargs)
        # Invalidate template list cache when new template is created
        invalidate_template_cache()
        return response
    
    def update(self, request, *args, **kwargs):
        """Override update to invalidate cache"""
        instance = self.get_object()
        response = super().update(request, *args, **kwargs)
        # Invalidate cache for this specific template and list
        invalidate_template_cache(template_id=instance.id)
        return response
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        purchased_count = instance.purchases.count()
        template_id = instance.id
        
        response = super().destroy(request, *args, **kwargs)
        
        # Invalidate cache for this template and list
        invalidate_template_cache(template_id=template_id)
        
        if purchased_count > 0:
            return Response(
                {
                    "message": f"Template deleted successfully. {purchased_count} purchased template(s) are now orphaned but preserved.",
                    "purchased_count": purchased_count
                },
                status=status.HTTP_200_OK
            )
        
        return response
    
    @cache_template_svg(timeout=1800)  # Cache for 30 minutes
    @action(detail=True, methods=['get'], url_path='svg')
    def get_svg(self, request, pk=None):
        """Separate endpoint to load SVG content for better UX"""
        # Create a minimal queryset without select_related/prefetch_related for SVG-only fetch
        template = Template.objects.only('svg').get(pk=pk)
        svg_content = template.svg
        
        if not svg_content:
            return Response({"svg": None}, status=status.HTTP_200_OK)
        
        # Add watermark for non-admin users
        is_admin = request.user.is_authenticated and request.user.is_staff
        if not is_admin:
            watermarked_svg = WaterMark().add_watermark(svg_content)
        else:
            watermarked_svg = svg_content
        
        return Response({"svg": watermarked_svg}, status=status.HTTP_200_OK)


class ToolViewSet(viewsets.ModelViewSet):
    queryset = Tool.objects.all().order_by('name')
    serializer_class = ToolSerializer
    permission_classes = [IsAdminOrReadOnly]
    
    def get_authenticators(self):
        if self.request.method in SAFE_METHODS:
            return []  # No authentication for GET/HEAD/OPTIONS
        return super().get_authenticators()


class FontViewSet(viewsets.ModelViewSet):
    queryset = Font.objects.all().order_by('name')
    serializer_class = FontSerializer
    permission_classes = [IsAdminOrReadOnly]
    
    def get_authenticators(self):
        if self.request.method in SAFE_METHODS:
            return []  # No authentication for GET/HEAD/OPTIONS
        return super().get_authenticators()


class PurchasedTemplatePagination(PageNumberPagination):
    """Pagination for PurchasedTemplate list views"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class PurchasedTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = PurchasedTemplateSerializer
    permission_classes = [IsOwnerOrAdmin]
    # No pagination for user-facing purchased template listings
    pagination_class = None

    def get_queryset(self): # type: ignore
        user = self.request.user
        queryset = PurchasedTemplate.objects.select_related('buyer', 'template').prefetch_related('template__fonts')
        
        if user.is_staff:
            queryset = queryset.all()
        else:
            queryset = queryset.filter(buyer=user)
        
        # For list views, defer large text fields to improve performance
        if self.action == 'list':
            queryset = queryset.defer('svg', 'form_fields')
        # For detail views, defer SVG to load it separately for better UX
        elif self.action == 'retrieve':
            queryset = queryset.defer('svg')
        
        queryset = queryset.order_by('-created_at')
        return queryset
    
    @action(detail=True, methods=['get'], url_path='svg')
    def get_svg(self, request, pk=None):
        """Separate endpoint to load SVG content for purchased templates"""
        # Create a minimal queryset without select_related/prefetch_related for SVG-only fetch
        user = request.user
        queryset = PurchasedTemplate.objects.only('svg', 'test')
        
        if not user.is_staff:
            queryset = queryset.filter(buyer=user)
        
        purchased_template = queryset.get(pk=pk)
        svg_content = purchased_template.svg
        
        if not svg_content:
            return Response({"svg": None}, status=status.HTTP_200_OK)
        
        # Add watermark if it's a test template
        if purchased_template.test:
            watermarked_svg = WaterMark().add_watermark(svg_content)
            return Response({"svg": watermarked_svg}, status=status.HTTP_200_OK)
        
        return Response({"svg": svg_content}, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        serializer.save(buyer=self.request.user)
        

class PublicTemplateTrackingView(APIView):
    permission_classes = [AllowAny]  # ✅ allows anyone
    authentication_classes = []      # ✅ disables auth

    def get(self, request, tracking_id):  # ✅ must include `request`
        try:
            purchased_template = PurchasedTemplate.objects.get(tracking_id=tracking_id)
            serializer = PurchasedTemplateSerializer(purchased_template)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except PurchasedTemplate.DoesNotExist:
            return Response({"detail": "Template not found."}, status=status.HTTP_404_NOT_FOUND)



class DownloadDoc(APIView):
    def post(self, request):
        print("=" * 60)
        print("=== DownloadDoc POST request started ===")
        print(f"User: {request.user.username if request.user.is_authenticated else 'Anonymous'}")
        
        output_type = request.data.get("type", "pdf").lower()
        purchased_template_id = request.data.get("purchased_template_id")
        template_name = request.data.get("template_name", "")
        side = request.data.get("side", "front")  # "front" or "back" for split downloads
        
        print(f"Output type: {output_type}")
        print(f"Purchased template ID: {purchased_template_id}")
        print(f"Template name: {template_name}")
        print(f"Side: {side}")

        # Optimize: Always fetch SVG from database instead of receiving it in request
        # This reduces request payload size significantly
        if not purchased_template_id:
            print("ERROR: purchased_template_id is required")
            return Response({"error": "purchased_template_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Optimize: Only fetch SVG and related fields needed for download
            # Use select_related for template (needed for keywords) but limit fields with only()
            # Use prefetch_related for fonts to efficiently load only font data
            purchased_template = PurchasedTemplate.objects.select_related('template').prefetch_related(
                'template__fonts'
            ).only(
                'svg', 'test', 'name', 'keywords', 
                'template__id', 'template__keywords'  # Only these template fields are loaded
            ).get(id=purchased_template_id, buyer=request.user)
            svg_content = purchased_template.svg
            if not template_name:
                template_name = purchased_template.name or ""
        except PurchasedTemplate.DoesNotExist:
            print("ERROR: Purchased template not found")
            return Response({"error": "Purchased template not found"}, status=status.HTTP_404_NOT_FOUND)

        if not svg_content or "</svg>" not in svg_content:
            print("ERROR: Invalid or missing SVG content")
            return Response({"error": "Invalid or missing SVG content"}, status=status.HTTP_400_BAD_REQUEST)

        if output_type not in ("pdf", "png"):
            print(f"ERROR: Unsupported output type: {output_type}")
            return Response({"error": "Unsupported type. Only 'pdf' and 'png' are allowed."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            print("Starting download processing...")
            # Sanitize template name for filename
            import re
            safe_name = re.sub(r'[^\w\s-]', '', template_name).strip() if template_name else ""
            safe_name = re.sub(r'[-\s]+', '-', safe_name) if safe_name else ""
            
            # Check if split-download is enabled
            split_direction = None
            if purchased_template:
                    # Check keywords from both purchased template and original template
                    keywords_to_check = []
                    if purchased_template.keywords:
                        keywords_to_check.extend(purchased_template.keywords)
                    if purchased_template.template and purchased_template.template.keywords:
                        keywords_to_check.extend(purchased_template.template.keywords)
                    
                    # Normalize keywords to strings and check
                    keywords_to_check = [str(k).lower().strip() for k in keywords_to_check if k]
                    
                    if "horizontal-split-download" in keywords_to_check:
                        split_direction = "horizontal"  # Horizontal keyword = cut left to right (top/bottom halves)
                    elif "vertical-split-download" in keywords_to_check:
                        split_direction = "vertical"  # Vertical keyword = cut top to bottom (left/right halves)
                    # Legacy support for old "split-download" keyword (defaults to horizontal split = left/right)
                    elif "split-download" in keywords_to_check:
                        split_direction = "horizontal"
                    
                    # Use template name from purchased template if not provided
                    if not safe_name and purchased_template.name:
                        safe_name = re.sub(r'[^\w\s-]', '', purchased_template.name).strip()
                        safe_name = re.sub(r'[-\s]+', '-', safe_name) if safe_name else ""
            
            # Inject fonts into SVG before conversion
            print("Checking for fonts to inject...")
            fonts_to_inject = []
            if purchased_template and purchased_template.template:
                # Optimize: Fonts are already prefetched, just access them
                # The prefetch_related('template__fonts') already loaded fonts efficiently
                fonts_to_inject = list(purchased_template.template.fonts.all())
                # Ensure we only use the fields we need (already optimized by prefetch)
                print(f"Found {len(fonts_to_inject)} font(s) to inject")
                for font in fonts_to_inject:
                    print(f"  - Font: {font.name} (ID: {font.id})")
            
            # Choose renderer based on output type and font requirements
            has_fonts = bool(fonts_to_inject)
            print(f"Has fonts: {has_fonts}")
            print(f"Playwright available: {PLAYWRIGHT_AVAILABLE}")
            
            if has_fonts:
                print("Injecting fonts into SVG...")
                try:
                    # Inject fonts with base64 embedding for Playwright
                    svg_with_fonts = inject_fonts_into_svg(svg_content, fonts_to_inject, embed_base64=True)
                    print(f"Font injection complete. SVG length after injection: {len(svg_with_fonts)}")
                except Exception as e:
                    print(f"ERROR: Font injection failed: {str(e)}")
                    import traceback
                    print(traceback.format_exc())
                    raise
                
                if output_type == "pdf":
                    print("Rendering PDF with fonts...")
                    # Use Playwright for PDF with fonts
                    if PLAYWRIGHT_AVAILABLE:
                        try:
                            print("Using Playwright for PDF rendering...")
                            output = render_svg_with_playwright(svg_with_fonts, "pdf")
                            print(f"SUCCESS: Playwright PDF rendering successful. Output size: {len(output)} bytes")
                        except Exception as e:
                            print(f"ERROR: Playwright PDF rendering failed: {str(e)}")
                            import traceback
                            print(traceback.format_exc())
                            print("Falling back to CairoSVG...")
                            # Fallback to CairoSVG (may not render fonts correctly)
                            output = cairosvg.svg2pdf(bytestring=svg_content.encode("utf-8"))
                            print(f"CairoSVG PDF rendering complete. Output size: {len(output)} bytes")
                    else:
                        print("WARNING: Playwright not available, using CairoSVG...")
                        # Fallback to CairoSVG if Playwright not available
                        output = cairosvg.svg2pdf(bytestring=svg_content.encode("utf-8"))
                        print(f"CairoSVG PDF rendering complete. Output size: {len(output)} bytes")
                else:  # PNG
                    print("Rendering PNG with fonts...")
                    # Use Playwright for PNG with fonts
                    if PLAYWRIGHT_AVAILABLE:
                        try:
                            print("Using Playwright for PNG rendering...")
                            output = render_svg_with_playwright(svg_with_fonts, "png")
                            print(f"SUCCESS: Playwright PNG rendering successful. Output size: {len(output)} bytes")
                        except Exception as e:
                            print(f"ERROR: Playwright PNG rendering failed: {str(e)}")
                            import traceback
                            print(traceback.format_exc())
                            print("Falling back to CairoSVG...")
                            # Fallback to CairoSVG (may not render fonts correctly)
                            output = cairosvg.svg2png(bytestring=svg_content.encode("utf-8"))
                            print(f"CairoSVG PNG rendering complete. Output size: {len(output)} bytes")
                    else:
                        print("WARNING: Playwright not available, using CairoSVG...")
                        # Fallback to CairoSVG if Playwright not available
                        output = cairosvg.svg2png(bytestring=svg_content.encode("utf-8"))
                        print(f"CairoSVG PNG rendering complete. Output size: {len(output)} bytes")
            else:
                print("No fonts detected, using CairoSVG...")
                # No fonts - use CairoSVG (fastest option)
                if output_type == "pdf":
                    print("Rendering PDF with CairoSVG...")
                    output = cairosvg.svg2pdf(bytestring=svg_content.encode("utf-8"))
                    print(f"CairoSVG PDF rendering complete. Output size: {len(output)} bytes")
                else:  # PNG
                    print("Rendering PNG with CairoSVG...")
                    output = cairosvg.svg2png(bytestring=svg_content.encode("utf-8"))
                    print(f"CairoSVG PNG rendering complete. Output size: {len(output)} bytes")
            
            # Set content type and filename
            if output_type == "pdf":
                content_type = "application/pdf"
                filename = f"{safe_name}.pdf" if safe_name else "output.pdf"
            else:  # PNG
                content_type = "image/png"
                filename = f"{safe_name}.png" if safe_name else "output.png"

            # Update user download count before handling response
            print("Updating user download count...")
            user = request.user
            user.downloads += 1
            user.save()
            
            # Handle split download
            if split_direction:
                print(f"Handling split download: {split_direction}, side: {side}")
                return self._handle_split_download(output, output_type, user, safe_name, split_direction, side)
            
            # Normal download
            print("Preparing response...")
            
            response = HttpResponse(output, content_type=content_type)
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            print(f"SUCCESS: Download complete. Filename: {filename}, Size: {len(output)} bytes")
            print("=" * 60)
            return response

        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            print("=" * 60)
            print("ERROR: DOWNLOAD ERROR OCCURRED")
            print(f"Error message: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            print("Full traceback:")
            print(error_traceback)
            print("=" * 60)
            return Response({"error": str(e), "traceback": error_traceback}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _handle_split_download(self, output, output_type, user, safe_name="", split_direction="horizontal", side="front"):
        """Split the output into two equal halves and return only the requested side
        
        Args:
            output: The image/PDF bytes
            output_type: "png" or "pdf"
            user: User object
            safe_name: Sanitized template name for filename
            split_direction: "horizontal" (left/right) or "vertical" (top/bottom)
            side: "front" (first half) or "back" (second half)
        """
        import io
        from PIL import Image
        
        print(f"[Split Download] Starting split download...")
        print(f"[Split Download] Output type: {output_type}")
        print(f"[Split Download] Split direction: {split_direction}")
        print(f"[Split Download] Side: {side}")
        print(f"[Split Download] Output size: {len(output)} bytes")
        
        try:
            if output_type == "png":
                print("[Split Download] Processing PNG...")
                # Split PNG image
                print("[Split Download] Opening image from bytes...")
                image = Image.open(io.BytesIO(output))
                width, height = image.size
                print(f"[Split Download] Image dimensions: {width}x{height}")
                
                selected_half = None
                
                if split_direction == "vertical":
                    print("[Split Download] Splitting vertically (left/right)...")
                    # Vertical keyword = cut from top to bottom => left/right halves
                    left_half = image.crop((0, 0, width // 2, height))  # Front (first half)
                    right_half = image.crop((width // 2, 0, width, height))  # Back (second half)
                    
                    if side == "front":
                        print("[Split Download] Returning left half (front)...")
                        selected_half = left_half
                    else:
                        print("[Split Download] Returning right half (back)...")
                        selected_half = right_half
                else:
                    print("[Split Download] Splitting horizontally (top/bottom)...")
                    # Horizontal keyword = cut from left to right => top/bottom halves
                    top_half = image.crop((0, 0, width, height // 2))  # Front (first half)
                    bottom_half = image.crop((0, height // 2, width, height))  # Back (second half)
                    
                    if side == "front":
                        print("[Split Download] Returning top half (front)...")
                        selected_half = top_half
                    else:
                        print("[Split Download] Returning bottom half (back)...")
                        selected_half = bottom_half
                
                # Save selected half to bytes
                print("[Split Download] Saving selected half...")
                half_buffer = io.BytesIO()
                selected_half.save(half_buffer, format='PNG')
                half_bytes = half_buffer.getvalue()
                print(f"[Split Download] Half saved. Size: {len(half_bytes)} bytes")
                
                # Create response with single file
                filename = f"{safe_name}_{side}.png" if safe_name else f"document_{side}.png"
                print("[Split Download] Creating HTTP response...")
                response = HttpResponse(half_bytes, content_type='image/png')
                response["Content-Disposition"] = f'attachment; filename="{filename}"'
                print(f"[Split Download] SUCCESS: Split download complete. Filename: {filename}")
                return response
                
            else:  # PDF
                print("[Split Download] Processing PDF...")
                # Convert PDF to image first, then split
                try:
                    from pdf2image import convert_from_bytes
                except ImportError:
                    print("[Split Download] ERROR: pdf2image not installed")
                    return Response(
                        {"error": "PDF splitting requires pdf2image. Install with: pip install pdf2image"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                
                # Convert PDF to image
                print("[Split Download] Converting PDF to image...")
                try:
                    images = convert_from_bytes(output)
                    if not images:
                        print("[Split Download] ERROR: PDF conversion returned no images")
                        return Response({"error": "Failed to convert PDF to image"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    print(f"[Split Download] PDF converted to {len(images)} image(s)")
                except Exception as e:
                    print(f"[Split Download] ERROR: PDF conversion failed: {str(e)}")
                    import traceback
                    print(traceback.format_exc())
                    # Check if it's a poppler error (check both exception type and message)
                    from pdf2image.exceptions import PDFInfoNotInstalledError
                    if isinstance(e, PDFInfoNotInstalledError) or "poppler" in str(e).lower() or "pdfinfo" in str(e).lower():
                        return Response(
                            {
                                "error": "PDF splitting requires poppler-utils to be installed.",
                                "installation_command": "sudo apt-get install poppler-utils",
                                "details": "Run this command in your terminal: sudo apt-get install poppler-utils"
                            },
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )
                    raise
                
                # Take first page (assuming single page PDF)
                image = images[0]
                width, height = image.size
                print(f"[Split Download] Image dimensions: {width}x{height}")
                
                selected_half = None
                
                if split_direction == "vertical":
                    print("[Split Download] Splitting vertically (left/right)...")
                    # Vertical keyword = cut from top to bottom => left/right halves
                    left_half = image.crop((0, 0, width // 2, height))  # Front (first half)
                    right_half = image.crop((width // 2, 0, width, height))  # Back (second half)
                    
                    if side == "front":
                        print("[Split Download] Returning left half (front)...")
                        selected_half = left_half
                    else:
                        print("[Split Download] Returning right half (back)...")
                        selected_half = right_half
                else:
                    print("[Split Download] Splitting horizontally (top/bottom)...")
                    # Horizontal keyword = cut from left to right => top/bottom halves
                    top_half = image.crop((0, 0, width, height // 2))  # Front (first half)
                    bottom_half = image.crop((0, height // 2, width, height))  # Back (second half)
                    
                    if side == "front":
                        print("[Split Download] Returning top half (front)...")
                        selected_half = top_half
                    else:
                        print("[Split Download] Returning bottom half (back)...")
                        selected_half = bottom_half
                
                # Save selected half to bytes as PNG (PDF splitting returns PNG)
                print("[Split Download] Saving selected half...")
                half_buffer = io.BytesIO()
                selected_half.save(half_buffer, format='PNG')
                half_bytes = half_buffer.getvalue()
                print(f"[Split Download] Half saved. Size: {len(half_bytes)} bytes")
                
                # Create response with single file
                filename = f"{safe_name}_{side}.png" if safe_name else f"document_{side}.png"
                print("[Split Download] Creating HTTP response...")
                response = HttpResponse(half_bytes, content_type='image/png')
                response["Content-Disposition"] = f'attachment; filename="{filename}"'
                print(f"[Split Download] SUCCESS: Split download complete. Filename: {filename}")
                return response
                
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            print("=" * 60)
            print("[Split Download] ERROR: Split download failed")
            print(f"[Split Download] Error message: {str(e)}")
            print(f"[Split Download] Error type: {type(e).__name__}")
            print("[Split Download] Full traceback:")
            print(error_traceback)
            print("=" * 60)
            return Response({"error": f"Failed to split document: {str(e)}", "traceback": error_traceback}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RemoveBackgroundView(APIView):
    """
    API endpoint to remove background from uploaded images using Remove.bg API
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            from django.conf import settings
            import base64
            import requests as req
            
            # Get the uploaded file from request
            uploaded_file = request.FILES.get('image')
            if not uploaded_file:
                return Response(
                    {"error": "No image file provided"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            print(f"Processing uploaded file: {uploaded_file.name}, size: {uploaded_file.size} bytes")
            
            # Validate file
            if uploaded_file.size == 0:
                return Response(
                    {"error": "Empty file provided"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if uploaded_file.size > 10 * 1024 * 1024:  # 10MB limit
                return Response(
                    {"error": "File too large (max 10MB)"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check wallet balance FIRST before calling API
            user = request.user
            charge_amount = 0.20
            
            if not hasattr(user, "wallet"):
                return Response(
                    {"error": "User does not have a wallet."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if user.wallet.balance < charge_amount:
                return Response(
                    {"error": "Insufficient wallet balance. You need at least $0.20 for background removal."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if API key is configured
            api_key = settings.REMOVEBG_API_KEY
            if not api_key:
                return Response(
                    {"error": "Remove.bg API key not configured. Please add REMOVEBG_API_KEY to your .env file"}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Read the uploaded file
            image_data = uploaded_file.read()
            
            # Remove background using Remove.bg API directly
            print("Calling Remove.bg API...")
            response = req.post(
                'https://api.remove.bg/v1.0/removebg',
                files={'image_file': image_data},
                data={'size': 'auto'},
                headers={'X-Api-Key': api_key},
                timeout=30
            )
            
            if response.status_code == 200:
                # Debit the wallet AFTER successful API call
                user.wallet.debit(charge_amount, description="Background removal (Remove.bg)")
                print(f"Charged ${charge_amount} from wallet. New balance: ${user.wallet.balance}")
                
                # Send real-time wallet update to user
                from wallet.views import send_wallet_update
                send_wallet_update(user, False)
                
                # Convert to base64
                result_base64 = base64.b64encode(response.content).decode('utf-8')
                result_data_url = f"data:image/png;base64,{result_base64}"
                
                print("Background removed successfully")
                
                return Response({
                    "success": True,
                    "image": result_data_url,
                    "message": "Background removed successfully"
                })
            else:
                error_msg = response.json().get('errors', [{}])[0].get('title', 'Unknown error')
                print(f"Remove.bg API error: {error_msg}")
                raise Exception(f"Remove.bg API error: {error_msg}")
            
        except Exception as e:
            import logging
            import traceback
            logger = logging.getLogger(__name__)
            error_details = traceback.format_exc()
            logger.error(f"Background removal failed: {str(e)}\n{error_details}")
            print(f"ERROR: Background removal failed: {str(e)}")
            print(f"Traceback: {error_details}")
            
            return Response(
                {"error": f"Background removal failed: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TutorialViewSet(viewsets.ModelViewSet):
    queryset = Tutorial.objects.select_related('template', 'template__tool').all()
    serializer_class = TutorialSerializer
    permission_classes = [IsAdminOrReadOnly]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        template_id = self.request.query_params.get('template')
        tool_id = self.request.query_params.get('tool')
        
        if template_id:
            queryset = queryset.filter(template_id=template_id)
        if tool_id:
            queryset = queryset.filter(template__tool_id=tool_id)
        return queryset


class AdminTemplateViewSet(viewsets.ModelViewSet):
    """Admin-only viewset for templates without watermarks"""
    queryset = Template.objects.all().order_by('-created_at')
    serializer_class = AdminTemplateSerializer
    permission_classes = [IsAdminOnly]  # Only admin users can access
    # No pagination for admin template listings (matching user-facing views)
    pagination_class = None
    
    def get_queryset(self):
        queryset = Template.objects.select_related('tool', 'tutorial').prefetch_related('fonts')
        hot_param = self.request.query_params.get("hot")
        tool_param = self.request.query_params.get("tool")

        if hot_param is not None:
            # Convert string to boolean
            if hot_param.lower() == "true":
                queryset = queryset.filter(hot=True)
            elif hot_param.lower() == "false":
                queryset = queryset.filter(hot=False)
        
        if tool_param:
            queryset = queryset.filter(tool__id=tool_param)
        
        # For list views, defer large text fields to improve performance
        if self.action == 'list':
            queryset = queryset.defer('svg', 'form_fields')
        # For detail views, defer SVG to load it separately for better UX
        elif self.action == 'retrieve':
            queryset = queryset.defer('svg')
        
        queryset = queryset.order_by('-created_at')
        return queryset
    
    def list(self, request, *args, **kwargs):
        """Override list method"""
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        """Override retrieve - no caching for admin to ensure fresh data"""
        return super().retrieve(request, *args, **kwargs)
    
    @action(detail=True, methods=['get'], url_path='svg')
    def get_svg(self, request, pk=None):
        """Separate endpoint to load SVG content for admin (no watermark) - NO CACHING for immediate updates"""
        # Create a minimal queryset without select_related/prefetch_related for SVG-only fetch
        template = Template.objects.only('svg').get(pk=pk)
        svg_content = template.svg
        
        if not svg_content:
            return Response({"svg": None}, status=status.HTTP_200_OK)
        
        # Admin gets SVG without watermark
        return Response({"svg": svg_content}, status=status.HTTP_200_OK)
    
    def create(self, request, *args, **kwargs):
        """Override create to invalidate cache"""
        response = super().create(request, *args, **kwargs)
        invalidate_template_cache()
        return response
    
    def update(self, request, *args, **kwargs):
        """Override update to invalidate cache"""
        instance = self.get_object()
        response = super().update(request, *args, **kwargs)
        invalidate_template_cache(template_id=instance.id)
        return response
    
    def destroy(self, request, *args, **kwargs):
        """Override destroy to invalidate cache"""
        instance = self.get_object()
        template_id = instance.id
        response = super().destroy(request, *args, **kwargs)
        invalidate_template_cache(template_id=template_id)
        return response