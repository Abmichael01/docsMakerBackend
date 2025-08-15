from .serializers import *
from .permissions import *
from rest_framework.permissions import SAFE_METHODS
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
import cairosvg
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from rest_framework.pagination import PageNumberPagination
from wallet.models import Wallet, Transaction
from accounts.serializers import CustomUserDetailsSerializer
from django.shortcuts import get_object_or_404

User = get_user_model()


class AdminOverview(APIView):
    permission_classes = [IsAdminOrReadOnly]
    
    def get(self, request):
        """
        Get admin overview statistics including:
        - total_downloads: Sum of all user downloads
        - total_users: Count of all users
        - total_purchased_docs: Count of paid documents (test=False)
        - total_wallet_balance: Sum of all wallet balances
        """
        serializer = AdminOverviewSerializer()
        
        data = {
            'total_downloads': serializer.get_total_downloads(),
            'total_users': serializer.get_total_users(),
            'total_purchased_docs': serializer.get_total_purchased_docs(),
            'total_wallet_balance': serializer.get_total_wallet_balance(),
        }
        return Response(data, status=status.HTTP_200_OK)


class AdminUsers(APIView):
    permission_classes = [IsAdminOrReadOnly]
    
    def get(self, request):
        """
        Get users data for the Users admin page with statistics:
        - all_users: Total number of users
        - new_users: New users for today, past 7/14/30 days
        - total_purchases_users: Users with purchases for today, past 7/14/30 days
        - users: Paginated user list
        
        Query Parameters:
        - page: Page number (default: 1)
        - page_size: Items per page (default: 10)
        - search: Search term to filter users by username or email
        """
        try:
            # Get query parameters
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 10))
            search = request.GET.get('search', '').strip()
            
            # Base queryset
            users_queryset = User.objects.all()
            
            # Apply search filter if search parameter is provided
            if search:
                users_queryset = users_queryset.filter(
                    Q(username__icontains=search) | 
                    Q(email__icontains=search)
                )
            
            # Get all users count (with search filter applied)
            all_users = users_queryset.count()
            
            # Get new users statistics (with search filter applied)
            now = timezone.now()
            today = now.date()
            seven_days_ago = today - timedelta(days=7)
            fourteen_days_ago = today - timedelta(days=14)
            thirty_days_ago = today - timedelta(days=30)
            
            new_users = {
                'today': users_queryset.filter(date_joined__date=today).count(),
                'past_7_days': users_queryset.filter(date_joined__date__gte=seven_days_ago).count(),
                'past_14_days': users_queryset.filter(date_joined__date__gte=fourteen_days_ago).count(),
                'past_30_days': users_queryset.filter(date_joined__date__gte=thirty_days_ago).count(),
            }
            
            # Get users with purchases statistics (with search filter applied)
            total_purchases_users = {
                'today': users_queryset.filter(
                    purchased_templates__test=False,
                    purchased_templates__created_at__date=today
                ).distinct().count(),
                'past_7_days': users_queryset.filter(
                    purchased_templates__test=False,
                    purchased_templates__created_at__date__gte=seven_days_ago
                ).distinct().count(),
                'past_14_days': users_queryset.filter(
                    purchased_templates__test=False,
                    purchased_templates__created_at__date__gte=fourteen_days_ago
                ).distinct().count(),
                'past_30_days': users_queryset.filter(
                    purchased_templates__test=False,
                    purchased_templates__created_at__date__gte=thirty_days_ago
                ).distinct().count(),
            }
            
            # Get paginated users (with search filter applied)
            paginator = PageNumberPagination()
            paginator.page_size = page_size
            
            # Order by date joined (newest first)
            users_queryset = users_queryset.order_by('-date_joined')
            paginated_users = paginator.paginate_queryset(users_queryset, request)
            
            user_serializer = CustomUserDetailsSerializer(paginated_users, many=True)
            
            users_data = {
                'results': user_serializer.data,
                'count': paginator.page.paginator.count,
                'next': paginator.get_next_link(),
                'previous': paginator.get_previous_link(),
                'current_page': page,
                'total_pages': paginator.page.paginator.num_pages,
            }
            
            data = {
                'all_users': all_users,
                'new_users': new_users,
                'total_purchases_users': total_purchases_users,
                'users': users_data,
                'search_term': search,  # Include the search term in response
            }
            
            return Response(data, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"Error in AdminUsers view: {str(e)}")
            return Response(
                {'error': 'Internal server error', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminUserDetails(APIView):
    permission_classes = [IsAdminOrReadOnly]
    
    def get(self, request, user_id):
        """
        Get detailed information about a specific user including:
        - User details
        - Wallet information
        - Purchase history
        - Wallet transaction history
        """
        try:
            # Get user or return 404
            user = get_object_or_404(User, id=user_id)
            
            # Get user details
            user_serializer = CustomUserDetailsSerializer(user)
            user_data = user_serializer.data
            
            # Get wallet information
            wallet_data = None
            try:
                wallet = user.wallet
                wallet_data = {
                    'id': str(wallet.id),
                    'balance': float(wallet.balance),
                    'created_at': wallet.user.date_joined.isoformat(),
                }
            except:
                wallet_data = {
                    'id': None,
                    'balance': 0.0,
                    'created_at': user.date_joined.isoformat(),
                }
            
            # Get purchase history
            purchases = user.purchased_templates.all().order_by('-created_at')
            purchase_history = []
            for purchase in purchases:
                purchase_history.append({
                    'id': str(purchase.id),
                    'template_name': purchase.template.name,
                    'name': purchase.name,
                    'test': purchase.test,
                    'status': purchase.status,
                    'tracking_id': purchase.tracking_id,
                    'created_at': purchase.created_at.isoformat(),
                    'updated_at': purchase.updated_at.isoformat(),
                })
            
            # Get wallet transaction history
            transaction_history = []
            try:
                transactions = user.wallet.transactions.all().order_by('-created_at')
                for transaction in transactions:
                    transaction_history.append({
                        'id': str(transaction.id),
                        'type': transaction.type,
                        'amount': float(transaction.amount),
                        'status': transaction.status,
                        'description': transaction.description,
                        'tx_id': transaction.tx_id,
                        'address': transaction.address,
                        'created_at': transaction.created_at.isoformat(),
                    })
            except:
                pass  # No wallet or transactions
            
            # Get additional statistics
            stats = {
                'total_purchases': user.purchased_templates.count(),
                'paid_purchases': user.purchased_templates.filter(test=False).count(),
                'test_purchases': user.purchased_templates.filter(test=True).count(),
                'total_downloads': user.downloads,
                'days_since_joined': (timezone.now() - user.date_joined).days,
            }
            
            data = {
                'user': user_data,
                'wallet': wallet_data,
                'purchase_history': purchase_history,
                'transaction_history': transaction_history,
                'stats': stats,
            }
            
            return Response(data, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"Error in AdminUserDetails view: {str(e)}")
            return Response(
                {'error': 'Internal server error', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request, user_id):
        """
        Delete a user and all associated data
        """
        try:
            # Get user or return 404
            user = get_object_or_404(User, id=user_id)
            
            # Prevent deletion of superusers
            if user.is_superuser:
                return Response(
                    {'error': 'Cannot delete superuser'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Store user info for response
            user_info = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
            }
            
            # Delete the user (this will cascade delete related data)
            user.delete()
            
            return Response(
                {
                    'message': 'User deleted successfully',
                    'deleted_user': user_info
                }, 
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            print(f"Error in AdminUserDetails delete: {str(e)}")
            return Response(
                {'error': 'Internal server error', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        


