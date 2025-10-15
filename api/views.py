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
    queryset = Tutorial.objects.all()
    serializer_class = TutorialSerializer
    permission_classes = [IsAdminOrReadOnly]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        template_id = self.request.query_params.get('template')
        if template_id:
            queryset = queryset.filter(template_id=template_id)
        return queryset