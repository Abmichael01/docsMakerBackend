from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from wallet.models import Transaction
from .models import VisitorLog

class LogVisitView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        path = request.data.get('path', '')
        # Only log if path is valid (simple check)
        if not path:
            return Response({"status": "ignored"})
            
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')

        # Create log
        VisitorLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            ip_address=ip,
            session_key=request.session.session_key,
            path=path[:255],
            method='VIEW', 
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response({"status": "ok"})


class AnalyticsDashboardView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        days = 30
        start_date = timezone.now() - timedelta(days=days)

        # 1. Visitor Stats (Daily)
        visitor_stats = VisitorLog.objects.filter(
            timestamp__gte=start_date
        ).annotate(
            date=TruncDate('timestamp')
        ).values('date').annotate(
            total_visits=Count('id'),
            unique_visitors=Count('ip_address', distinct=True) # or session_key
        ).order_by('date')

        # 2. Wallet Inflow (Daily Revenue)
        revenue_stats = Transaction.objects.filter(
            created_at__gte=start_date,
            type=Transaction.Type.PAYMENT, # Assuming this is a sale
            status=Transaction.Status.COMPLETED
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            total_sales=Count('id'),
            total_revenue=Sum('amount') 
        ).order_by('date')

        # Merge Data
        stats_map = {}
        
        # Init map
        for i in range(days + 1):
            d = (timezone.now() - timedelta(days=days - i)).date()
            stats_map[str(d)] = {
                "date": str(d),
                "total_visits": 0,
                "unique_visitors": 0,
                "total_sales": 0,
                "total_revenue": 0
            }

        for item in visitor_stats:
            d = str(item['date'])
            if d in stats_map:
                stats_map[d]['total_visits'] = item['total_visits']
                stats_map[d]['unique_visitors'] = item['unique_visitors']

        for item in revenue_stats:
            d = str(item['date'])
            if d in stats_map:
                stats_map[d]['total_sales'] = item['total_sales']
                # abs() because payments are negative
                stats_map[d]['total_revenue'] = abs(float(item['total_revenue'] or 0))

        # 3. Recent Unique Visitors
        # Fetch logs for today
        recent_logs = VisitorLog.objects.filter(
            timestamp__date=timezone.now().date()
        ).select_related('user').order_by('-timestamp').values(
            'ip_address', 'path', 'timestamp', 'user__username', 'method'
        )
        
        # Process in Python to get unique IPs with their latest activity
        unique_ips = set()
        unique_visitors = []
        for log in recent_logs:
            if log['ip_address'] not in unique_ips:
                unique_visitors.append(log)
                unique_ips.add(log['ip_address'])
                if len(unique_visitors) >= 100:
                    break

        return Response({
            "chart_data": list(stats_map.values()),
            "recent_visitors": unique_visitors,
            "device_stats": [
                {
                    "device": "Mobile",
                    "count": VisitorLog.objects.filter(timestamp__gte=start_date, user_agent__icontains="Mobile").exclude(user_agent__icontains="Tablet").count()
                },
                {
                    "device": "Desktop",
                    "count": VisitorLog.objects.filter(timestamp__gte=start_date).exclude(user_agent__icontains="Mobile").exclude(user_agent__icontains="Tablet").count()
                },
                }
            ]
        })

from rest_framework import viewsets
from .models import AuditLog
from .serializers import AuditLogSerializer

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for Audit Logs. Restricted to Admins.
    """
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminUser] # Staff can view logs? Let's allow IsAdminUser
    
    def get_queryset(self):
        return AuditLog.objects.select_related('actor').order_by('-timestamp')
