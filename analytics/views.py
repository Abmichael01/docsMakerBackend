from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import datetime, time, timedelta
from api.utils.admin_ranges import get_date_window, get_range_label, parse_days_param
from wallet.models import Transaction
from rest_framework import viewsets
from .models import VisitorLog, Campaign
from .serializers import VisitorLogSerializer, CampaignSerializer
from accounts.models import User
from .services import record_visit
from .utils import build_source_label


def build_campaign_match_q(campaign_record):
    source = campaign_record.source or campaign_record.name
    medium = campaign_record.medium or 'custom'

    query = Q(source=source, medium=medium)

    if campaign_record.campaign:
        query &= Q(campaign=campaign_record.campaign)
    if campaign_record.content:
        query &= Q(content=campaign_record.content)
    if campaign_record.term:
        query &= Q(term=campaign_record.term)
    if campaign_record.source_platform:
        query &= Q(source_platform=campaign_record.source_platform)

    return query


class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.all()
    serializer_class = CampaignSerializer
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get aggregated stats for all campaigns.
        """
        today = timezone.localdate()
        campaigns = Campaign.objects.all()
        total_sources = campaigns.count()

        combined_query = Q(pk__in=[])
        for campaign_record in campaigns:
            combined_query |= build_campaign_match_q(campaign_record)

        campaign_visit_queryset = VisitorLog.objects.filter(combined_query, is_bot=False) if total_sources else VisitorLog.objects.none()
        total_traffic = campaign_visit_queryset.count()

        breakdown = []
        for c in campaigns:
            visit_query = build_campaign_match_q(c)
            c_visits = VisitorLog.objects.filter(visit_query, is_bot=False).count()

            user_query = Q(source=c.source or c.name)
            if c.medium:
                user_query &= Q(medium=c.medium)
            if c.campaign:
                user_query &= Q(campaign=c.campaign)

            c_users = User.objects.filter(user_query).count()
            breakdown.append({
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "source": c.source,
                "medium": c.medium,
                "campaign": c.campaign,
                "content": c.content,
                "term": c.term,
                "source_platform": c.source_platform,
                "landing_path": c.landing_path,
                "ref_code": c.ref_code,
                "visits": c_visits,
                "users": c_users,
                "created_at": c.created_at
            })

        active_today = sum(
            1
            for campaign_record in campaigns
            if VisitorLog.objects.filter(
                build_campaign_match_q(campaign_record),
                is_bot=False,
                timestamp__date=today,
            ).exists()
        )

        return Response({
            "total_sources": total_sources,
            "total_traffic": total_traffic,
            "active_today": active_today,
            "campaigns": breakdown
        })

class LogVisitView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        path = request.data.get('path', '')
        attribution_payload = request.data.get('attribution') or {}

        if not path:
            return Response({"status": "ignored"})

        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        _log_instance, visitor_payload = record_visit(
            path=path,
            attribution_payload=attribution_payload,
            request=request,
        )

        # Broadcast to Admins
        async_to_sync(channel_layer.group_send)(
            "admin_activity",
            {
                "type": "activity_event",
                "data": {
                    "type": "new_visit",
                    "visitor": visitor_payload,
                }
            }
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
        online_now = VisitorLog.objects.filter(
            timestamp__gte=five_mins_ago,
            is_bot=False
        ).values('visitor_id').distinct().count()

        visit_queryset = VisitorLog.objects.filter(
            timestamp__range=(start_datetime, end_datetime),
            is_bot=False
        )

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
            unique_visitors=Count('visitor_id', distinct=True)
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
            .values(
                'id',
                'ip_address',
                'visitor_id',
                'session_key',
                'path',
                'timestamp',
                'user__username',
                'method',
                'source',
                'medium',
                'campaign',
                'channel_group',
            )
        )[:1000]

        unique_visitors_map = {}
        for log in recent_logs:
            # Identify the visitor: Prioritize actual User, then Persistent ID, then Session/IP
            visitor_key = (
                log['user__username']
                or log['visitor_id']
                or log['ip_address']
                or log['session_key']
                or f"guest:{log['path']}:{log['timestamp']}"
            )



            if visitor_key not in unique_visitors_map:
                unique_visitors_map[visitor_key] = {
                    **log,
                    'source_label': build_source_label(log.get('source'), log.get('medium')),
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
            unique_visitors=Count('visitor_id', distinct=True),
            authenticated_visits=Count('id', filter=Q(user__isnull=False)),
            guest_visits=Count('id', filter=Q(user__isnull=True)),
        )


        payment_summary = completed_payments.aggregate(
            total_sales=Count('id'),
            total_revenue=Sum('amount'),
        )

        source_stats = list(
            visit_queryset
            .filter(source__isnull=False)
            .values('source', 'medium')
            .annotate(
                visits=Count('id'),
                unique_visitors=Count('visitor_id', distinct=True)
            )
            .order_by('-visits')[:10]
        )
        source_stats = [
            {
                **item,
                'source': build_source_label(item.get('source'), item.get('medium')),
            }
            for item in source_stats
        ]

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
            "source_stats": source_stats,
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
        source = request.GET.get('source')

        queryset = VisitorLog.objects.select_related('user').filter(is_bot=False).order_by('-timestamp')

        if source:
            queryset = queryset.filter(
                Q(source__icontains=source) |
                Q(medium__icontains=source) |
                Q(campaign__icontains=source)
            )

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
                Q(source__icontains=search) |
                Q(medium__icontains=search) |
                Q(campaign__icontains=search) |
                Q(user__username__icontains=search)
            )

        paginator = ActivityLogPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = VisitorLogSerializer(page, many=True)
        return paginator.get_indicated_response(serializer.data) if hasattr(paginator, 'get_indicated_response') else paginator.get_paginated_response(serializer.data)
