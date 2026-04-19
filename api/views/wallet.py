from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework import status
from django.db.models import Sum, Count
from django.utils import timezone
from api.serializers.wallet import WalletSerializer, TransactionSerializer
from api.utils.admin_ranges import get_date_window, get_range_label, parse_days_param
from wallet.models import Wallet, Transaction

class WalletStatsView(APIView):
    """Get wallet statistics for admin dashboard"""
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        days = parse_days_param(request.GET.get('days'), default=1)
        _today, _start_date, start_datetime = get_date_window(days)

        # Total balance — regular users only (excludes admin/staff wallets)
        total_balance = Wallet.objects.filter(
            user__is_staff=False, user__is_superuser=False
        ).aggregate(total=Sum('balance'))['total'] or 0

        period_transactions = Transaction.objects.filter(
            created_at__gte=start_datetime,
            status=Transaction.Status.COMPLETED,
            wallet__user__is_staff=False,
            wallet__user__is_superuser=False,
        )

        total_inflow = period_transactions.filter(
            type=Transaction.Type.DEPOSIT
        ).aggregate(total=Sum('amount'))['total'] or 0

        total_outflow = period_transactions.filter(
            type=Transaction.Type.PAYMENT
        ).aggregate(total=Sum('amount'))['total'] or 0

        transaction_count = period_transactions.count()
        funded_wallets = period_transactions.filter(
            type=Transaction.Type.DEPOSIT
        ).aggregate(total=Count('wallet_id', distinct=True))['total'] or 0

        response = Response({
            'totalBalance': float(total_balance),
            'totalInflow': float(total_inflow),
            'totalOutflow': abs(float(total_outflow)),
            'netFlow': float(total_inflow) - abs(float(total_outflow)),
            'transactionCount': transaction_count,
            'fundedWallets': funded_wallets,
            'rangeDays': days,
            'rangeLabel': get_range_label(days),
        })
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response


class WalletListView(APIView):
    """List all user wallets"""
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        # Only list wallets of regular users (excludes admin/staff)
        wallets = Wallet.objects.select_related('user').filter(
            user__is_staff=False, user__is_superuser=False
        )
        serializer = WalletSerializer(wallets, many=True)
        return Response(serializer.data)


class WalletAdjustView(APIView):
    """Manually adjust user wallet balance"""
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        wallet_id = request.data.get('walletId')
        adjustment_type = request.data.get('type')  # 'credit' or 'debit'
        amount = request.data.get('amount')
        reason = request.data.get('reason', '')
        
        if not all([wallet_id, adjustment_type, amount]):
            return Response(
                {'error': 'Missing required fields'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            wallet = Wallet.objects.get(id=wallet_id)
            
            if adjustment_type == 'credit':
                wallet.credit(amount, description=f"Admin adjustment: {reason}")
            elif adjustment_type == 'debit':
                wallet.debit(amount, description=f"Admin adjustment: {reason}")
            else:
                return Response(
                    {'error': 'Invalid adjustment type'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response({'message': 'Balance adjusted successfully'})
        except Wallet.DoesNotExist:
            return Response(
                {'error': 'Wallet not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class PendingRequestsView(APIView):
    """List pending funding requests"""
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        # TODO: Implement when FundingRequest model exists
        # For now, return empty list
        return Response([])


class ApproveRequestView(APIView):
    """Approve a funding request"""
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        # TODO: Implement when FundingRequest model exists
        return Response({'message': 'Request approved'})


class RejectRequestView(APIView):
    """Reject a funding request"""
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        # TODO: Implement when FundingRequest model exists
        return Response({'message': 'Request rejected'})


class TransactionHistoryView(APIView):
    """Get all wallet transactions"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        transactions = Transaction.objects.select_related('wallet__user').all().order_by('-created_at')
        serializer = TransactionSerializer(transactions, many=True)
        
        # Calculate stats
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        total_volume = Transaction.objects.filter(
            type='deposit'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        stats = {
            'total_count': Transaction.objects.count(),
            'total_volume': float(total_volume),
            'month_count': Transaction.objects.filter(created_at__gte=month_start).count(),
            'pending_count': Transaction.objects.filter(status='pending').count(),
        }
        
        return Response({
            'transactions': serializer.data,
            'stats': stats,
        })
