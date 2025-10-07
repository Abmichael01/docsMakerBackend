# templates/views.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Template, PurchasedTemplate, Tool, Tutorial
from .serializers import *
from .permissions import *
from rest_framework.permissions import SAFE_METHODS
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
import cairosvg


class TemplateViewSet(viewsets.ModelViewSet):
    queryset = Template.objects.all().order_by('-created_at')
    serializer_class = TemplateSerializer
    permission_classes = [IsAdminOrReadOnly]
    # authentication_classes = []
    
    def get_authenticators(self):
        if self.request.method in SAFE_METHODS:
            return []  # No authentication for GET/HEAD/OPTIONS
        return super().get_authenticators()
    
    def get_queryset(self):
        queryset = Template.objects.all().order_by('-created_at')
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
        
        return queryset
    
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        purchased_count = instance.purchases.count()
        
        response = super().destroy(request, *args, **kwargs)
        
        if purchased_count > 0:
            return Response(
                {
                    "message": f"Template deleted successfully. {purchased_count} purchased template(s) are now orphaned but preserved.",
                    "purchased_count": purchased_count
                },
                status=status.HTTP_200_OK
            )
        
        return response


class ToolViewSet(viewsets.ModelViewSet):
    queryset = Tool.objects.all().order_by('name')
    serializer_class = ToolSerializer
    permission_classes = [IsAdminOrReadOnly]
    
    def get_authenticators(self):
        if self.request.method in SAFE_METHODS:
            return []  # No authentication for GET/HEAD/OPTIONS
        return super().get_authenticators()


class PurchasedTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = PurchasedTemplateSerializer
    permission_classes = [IsOwnerOrAdmin]

    def get_queryset(self): # type: ignore
        user = self.request.user
        if user.is_staff:
            return PurchasedTemplate.objects.all().order_by('-created_at')
        return PurchasedTemplate.objects.filter(buyer=user).order_by('-created_at')

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
        svg_content = request.data.get("svg")
        output_type = request.data.get("type", "pdf").lower()

        if not svg_content or "</svg>" not in svg_content:
            return Response({"error": "Invalid or missing SVG content"}, status=status.HTTP_400_BAD_REQUEST)

        if output_type not in ("pdf", "png"):
            return Response({"error": "Unsupported type. Only 'pdf' and 'png' are allowed."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if output_type == "pdf":
                output = cairosvg.svg2pdf(bytestring=svg_content.encode("utf-8"))
                content_type = "application/pdf"
                filename = "output.pdf"
            else:  # PNG
                output = cairosvg.svg2png(bytestring=svg_content.encode("utf-8"))
                content_type = "image/png"
                filename = "output.png"

            user = request.user
            user.downloads += 1
            user.save()
            
            response = HttpResponse(output, content_type=content_type)
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RemoveBackgroundView(APIView):
    """
    API endpoint to remove background from uploaded images using OpenCV
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        temp_file_path = None
        try:
            import cv2
            import numpy as np
            from PIL import Image
            import base64
            import io
            import tempfile
            import os
            
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
            
            # Save uploaded file to temporary directory
            file_extension = uploaded_file.name.split('.')[-1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as temp_file:
                for chunk in uploaded_file.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
            
            print(f"Saved temporary file: {temp_file_path}")
            
            # Load image with OpenCV
            image = cv2.imread(temp_file_path)
            if image is None:
                return Response(
                    {"error": "Invalid image file"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            print(f"Loaded image: {image.shape}")
            
            # Convert to RGB
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Create a simple background removal using color-based segmentation
            # This is a basic approach - for better results, you'd need more sophisticated methods
            
            # Convert to HSV for better color segmentation
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # Create mask for white/light backgrounds (common in document photos)
            # Adjust these values based on your specific use case
            lower_white = np.array([0, 0, 200])
            upper_white = np.array([180, 30, 255])
            mask_white = cv2.inRange(hsv, lower_white, upper_white)
            
            # Create mask for light gray backgrounds
            lower_gray = np.array([0, 0, 150])
            upper_gray = np.array([180, 30, 200])
            mask_gray = cv2.inRange(hsv, lower_gray, upper_gray)
            
            # Combine masks
            mask = cv2.bitwise_or(mask_white, mask_gray)
            
            # Apply morphological operations to clean up the mask
            kernel = np.ones((3,3), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            
            # Invert mask (we want to keep the foreground, remove background)
            mask = cv2.bitwise_not(mask)
            
            # Apply mask to create transparent background
            # Convert to RGBA
            image_rgba = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2RGBA)
            
            # Set alpha channel based on mask
            image_rgba[:, :, 3] = mask
            
            # Convert back to PIL Image
            pil_image = Image.fromarray(image_rgba, 'RGBA')
            
            # Convert to base64
            buffer = io.BytesIO()
            pil_image.save(buffer, format='PNG')
            img_bytes = buffer.getvalue()
            
            result_base64 = base64.b64encode(img_bytes).decode('utf-8')
            result_data_url = f"data:image/png;base64,{result_base64}"
            
            # Clean up temporary file
            os.unlink(temp_file_path)
            print(f"Cleaned up temporary file: {temp_file_path}")
            
            return Response({
                "success": True,
                "image": result_data_url,
                "message": "Background removed successfully using OpenCV"
            })
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Background removal failed: {str(e)}", exc_info=True)
            
            # Clean up temporary file if it exists
            try:
                if temp_file_path and os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    print(f"Cleaned up temporary file after error: {temp_file_path}")
            except:
                pass
            
            return Response(
                {"error": f"Background removal failed: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TutorialViewSet(viewsets.ModelViewSet):
    queryset = Tutorial.objects.all()
    serializer_class = TutorialSerializer
    permission_classes = [IsAdminOrReadOnly]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        template_id = self.request.query_params.get('template')
        if template_id:
            queryset = queryset.filter(template_id=template_id)
        return queryset