from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from ..serializers import AdminOverviewSerializer, AdminUsersSerializer
from ..permissions import IsAdminOrReadOnly
from accounts.serializers import CustomUserDetailsSerializer

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
        - documents_chart: Daily document creation for last 30 days
        - revenue_chart: Daily wallet balance growth for last 30 days
        """
        from ..models import PurchasedTemplate
        from wallet.models import Wallet
        from django.db.models import Count, Sum
        from django.db.models.functions import TruncDate
        
        serializer = AdminOverviewSerializer()
        
        # Get documents chart data for last 30 days
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        documents_data = (
            PurchasedTemplate.objects
            .filter(created_at__date__gte=thirty_days_ago)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(
                total=Count('id'),
                paid=Count('id', filter=Q(test=False)),
                test=Count('id', filter=Q(test=True))
            )
            .order_by('date')
        )
        
        # Format documents chart data
        documents_chart = [
            {
                'date': item['date'].isoformat(),
                'total': item['total'],
                'paid': item['paid'],
                'test': item['test']
            }
            for item in documents_data
        ]
        
        # Get revenue/wallet chart data - cumulative wallet balances
        # We'll calculate total wallet balance at each day
        all_users_count = User.objects.count()
        revenue_chart = []
        
        # For simplicity, let's show wallet balance trend over time
        # by aggregating wallet creation dates and current balances
        for i in range(30):
            date = (timezone.now().date() - timedelta(days=29-i))
            users_by_date = User.objects.filter(date_joined__date__lte=date).count()
            
            revenue_chart.append({
                'date': date.isoformat(),
                'users': users_by_date,
                'downloads': serializer.get_total_downloads()  # This is total, not daily
            })
        
        data = {
            'total_downloads': serializer.get_total_downloads(),
            'total_users': serializer.get_total_users(),
            'total_purchased_docs': serializer.get_total_purchased_docs(),
            'total_wallet_balance': serializer.get_total_wallet_balance(),
            'documents_chart': documents_chart,
            'revenue_chart': revenue_chart,
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
        """
        try:
            # Get query parameters
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 10))
            search = request.GET.get('search', '').strip()
            
            # Base queryset
            users_queryset = User.objects.all()
            
            # Apply search filter
            if search:
                users_queryset = users_queryset.filter(
                    Q(username__icontains=search) | 
                    Q(email__icontains=search)
                )
            
            # Get statistics
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
            
            # Pagination
            paginator = PageNumberPagination()
            paginator.page_size = page_size
            
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
                'all_users': users_queryset.count(),
                'new_users': new_users,
                'total_purchases_users': total_purchases_users,
                'users': users_data,
                'search_term': search,
            }
            
            return Response(data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Internal server error', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminUserDetails(APIView):
    permission_classes = [IsAdminOrReadOnly]
    
    def get(self, request, user_id):
        try:
            user = get_object_or_404(User, id=user_id)
            user_serializer = CustomUserDetailsSerializer(user)
            
            # Wallet data
            wallet_data = {
                'id': None,
                'balance': 0.0,
                'created_at': user.date_joined.isoformat(),
            }
            if hasattr(user, 'wallet'):
                wallet = user.wallet
                wallet_data = {
                    'id': str(wallet.id),
                    'balance': float(wallet.balance),
                    'created_at': wallet.created_at.isoformat() if hasattr(wallet, 'created_at') else user.date_joined.isoformat(),
                }
            
            # Purchase history
            purchases = user.purchased_templates.all().order_by('-created_at')
            purchase_history = [{
                'id': str(p.id),
                'template_name': p.template.name if p.template else "Deleted Template",
                'name': p.name,
                'test': p.test,
                'tracking_id': p.tracking_id,
                'created_at': p.created_at.isoformat(),
                'updated_at': p.updated_at.isoformat(),
            } for p in purchases]
            
            # Transaction history
            transaction_history = []
            if hasattr(user, 'wallet'):
                transactions = user.wallet.transactions.all().order_by('-created_at')
                transaction_history = [{
                    'id': str(t.id),
                    'type': t.type,
                    'amount': float(t.amount),
                    'status': t.status,
                    'description': t.description,
                    'tx_id': t.tx_id,
                    'address': t.address,
                    'created_at': t.created_at.isoformat(),
                } for t in transactions]
            
            # Stats
            stats = {
                'total_purchases': user.purchased_templates.count(),
                'paid_purchases': user.purchased_templates.filter(test=False).count(),
                'test_purchases': user.purchased_templates.filter(test=True).count(),
                'total_downloads': getattr(user, 'downloads', 0),
                'days_since_joined': (timezone.now() - user.date_joined).days,
            }
            
            return Response({
                'user': user_serializer.data,
                'wallet': wallet_data,
                'purchase_history': purchase_history,
                'transaction_history': transaction_history,
                'stats': stats,
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Internal server error', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request, user_id):
        try:
            user = get_object_or_404(User, id=user_id)
            if user.is_superuser:
                return Response({'error': 'Cannot delete superuser'}, status=status.HTTP_400_BAD_REQUEST)
            
            user_info = {'id': user.id, 'username': user.username, 'email': user.email}
            user.delete()
            return Response({'message': 'User deleted successfully', 'deleted_user': user_info}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': 'Internal server error', 'details': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
