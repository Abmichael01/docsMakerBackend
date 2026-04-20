from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import datetime, time, timedelta
from api.utils.admin_ranges import get_date_window, get_range_label, parse_days_param
from wallet.models import Transaction
from .models import VisitorLog
from .serializers import VisitorLogSerializer

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
        date_str = request.GET.get('date')
        days = parse_days_param(request.GET.get('days'), default=1)
        
        # Calculate Time Window
        if date_str:
            try:
                selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                start_date = selected_date
                days = 1
                current_tz = timezone.get_current_timezone()
                start_datetime = timezone.make_aware(datetime.combine(start_date, time.min), current_tz)
                end_datetime = timezone.make_aware(datetime.combine(start_date, time.max), current_tz)
                range_label = selected_date.strftime('%b %d, %Y')
            except ValueError:
                _today, start_date, start_datetime = get_date_window(days)
                end_datetime = timezone.now()
                range_label = get_range_label(days)
        else:
            _today, start_date, start_datetime = get_date_window(days)
            end_datetime = timezone.now()
            range_label = get_range_label(days)

        # Real-time: Online Now (last 5 minutes)
        five_mins_ago = timezone.now() - timedelta(minutes=5)
        online_now = VisitorLog.objects.filter(timestamp__gte=five_mins_ago).values('ip_address', 'user_id').distinct().count()

        visit_queryset = VisitorLog.objects.filter(timestamp__range=(start_datetime, end_datetime))
        completed_payments = Transaction.objects.filter(
            created_at__range=(start_datetime, end_datetime),
            type=Transaction.Type.PAYMENT,
            status=Transaction.Status.COMPLETED,
        )

        # 1. Visitor Stats (Daily)
        visitor_stats = visit_queryset.annotate(
            date=TruncDate('timestamp')
        ).values('date').annotate(
            total_visits=Count('id'),
            unique_visitors=Count('ip_address', distinct=True)
        ).order_by('date')

        # 2. Wallet Inflow (Daily Revenue)
        revenue_stats = completed_payments.annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            total_sales=Count('id'),
            total_revenue=Sum('amount')
        ).order_by('date')

        # Merge Data
        stats_map = {}

        # Init map
        for i in range(days):
            d = start_date + timedelta(days=i)
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

        # 3. Recent visitors, grouped by latest unique activity in the selected range
        recent_logs = (
            visit_queryset
            .select_related('user')
            .order_by('-timestamp')
            .values('ip_address', 'session_key', 'path', 'timestamp', 'user__username', 'method')
        )[:1000]

        unique_visitors_map = {}
        for log in recent_logs:
            visitor_key = (
                log['ip_address']
                or log['session_key']
                or f"guest:{log['path']}:{log['timestamp']}"
            )

            if visitor_key not in unique_visitors_map:
                unique_visitors_map[visitor_key] = {
                    **log,
                    'visit_count': 0,
                }

            unique_visitors_map[visitor_key]['visit_count'] += 1

        unique_visitors = list(unique_visitors_map.values())[:24]

        top_pages = list(
            visit_queryset
            .values('path')
            .annotate(visits=Count('id'))
            .order_by('-visits', 'path')[:6]
        )

        visitor_summary = visit_queryset.aggregate(
            total_visits=Count('id'),
            unique_visitors=Count('ip_address', distinct=True),
            authenticated_visits=Count('id', filter=Q(user__isnull=False)),
            guest_visits=Count('id', filter=Q(user__isnull=True)),
        )

        payment_summary = completed_payments.aggregate(
            total_sales=Count('id'),
            total_revenue=Sum('amount'),
        )

        unique_count = visitor_summary['unique_visitors'] or 0
        sales_count = payment_summary['total_sales'] or 0

        response = Response({
            "chart_data": list(stats_map.values()),
            "recent_visitors": unique_visitors,
            "device_stats": [
                {
                    "device": "Mobile",
                    "count": visit_queryset.filter(user_agent__icontains="Mobile").exclude(
                        Q(user_agent__icontains="Tablet") | Q(user_agent__icontains="iPad")
                    ).count()
                },
                {
                    "device": "Desktop",
                    "count": visit_queryset.exclude(user_agent__icontains="Mobile").exclude(
                        Q(user_agent__icontains="Tablet") | Q(user_agent__icontains="iPad")
                    ).count()
                },
                {
                    "device": "Tablet",
                    "count": visit_queryset.filter(
                        Q(user_agent__icontains="Tablet") | Q(user_agent__icontains="iPad")
                    ).count()
                },
            ],
            "top_pages": top_pages,
            "range_days": days,
            "range_label": range_label,
            "summary": {
                "online_now": online_now,
                "total_visits": visitor_summary['total_visits'] or 0,
                "unique_visitors": unique_count,
                "authenticated_visits": visitor_summary['authenticated_visits'] or 0,
                "guest_visits": visitor_summary['guest_visits'] or 0,
                "total_sales": sales_count,
                "total_revenue": abs(float(payment_summary['total_revenue'] or 0)),
                "conversion_rate": round((sales_count / unique_count) * 100, 2) if unique_count else 0.0,
            },
        })
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response

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

from rest_framework.pagination import PageNumberPagination

class ActivityLogPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100

class UserActivityView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        date_str = request.GET.get('date')
        user_id = request.GET.get('user_id')
        search = request.GET.get('search')

        queryset = VisitorLog.objects.select_related('user').order_by('-timestamp')

        if date_str:
            try:
                selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                current_tz = timezone.get_current_timezone()
                start_datetime = timezone.make_aware(datetime.combine(selected_date, time.min), current_tz)
                end_datetime = timezone.make_aware(datetime.combine(selected_date, time.max), current_tz)
                queryset = queryset.filter(timestamp__range=(start_datetime, end_datetime))
            except ValueError:
                pass

        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        if search:
            queryset = queryset.filter(
                Q(ip_address__icontains=search) | 
                Q(path__icontains=search) | 
                Q(user__username__icontains=search)
            )

        paginator = ActivityLogPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = VisitorLogSerializer(page, many=True)
        return paginator.get_indicated_response(serializer.data) if hasattr(paginator, 'get_indicated_response') else paginator.get_paginated_response(serializer.data)
