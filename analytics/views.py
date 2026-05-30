from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny
from rest_framework.throttling import ScopedRateThrottle
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import datetime, time, timedelta
from api.utils.admin_ranges import get_admin_date_range, get_range_label, parse_days_param
from wallet.models import Transaction
from rest_framework import viewsets
from .models import VisitorLog, Campaign
from .serializers import VisitorLogSerializer, CampaignSerializer
from accounts.models import User
from .services import record_visit, ONLINE_SET_KEY
from .utils import build_source_label
from django.core.cache import cache


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
        Aggregated stats for all campaigns.

        Bulk-fetches all VisitorLog rows matching any campaign in ONE query,
        grouped maximally on the six matcher fields, plus today's subtotal.
        Per-campaign numbers are then reduced in Python — O(rows × campaigns)
        but with zero DB round-trips inside the loop.
        """
        today = timezone.localdate()
        campaigns = list(Campaign.objects.all())
        total_sources = len(campaigns)

        if not total_sources:
            return Response({
                "total_sources": 0,
                "total_traffic": 0,
                "active_today": 0,
                "campaigns": [],
            })

        combined_visit_q = Q(pk__in=[])
        combined_user_q = Q(pk__in=[])
        for c in campaigns:
            combined_visit_q |= build_campaign_match_q(c)
            uq = Q(source=c.source or c.name)
            if c.medium:
                uq &= Q(medium=c.medium)
            if c.campaign:
                uq &= Q(campaign=c.campaign)
            combined_user_q |= uq

        match_fields = ('source', 'medium', 'campaign', 'content', 'term', 'source_platform')

        visit_rows = list(
            VisitorLog.objects
            .filter(combined_visit_q, is_bot=False)
            .values(*match_fields)
            .annotate(
                visits=Count('id'),
                today_visits=Count('id', filter=Q(timestamp__date=today)),
            )
        )

        user_rows = list(
            User.objects
            .filter(combined_user_q)
            .values('source', 'medium', 'campaign')
            .annotate(n=Count('id'))
        )

        def _row_matches(row, c):
            """Row matches campaign iff every non-null campaign field equals the row's value."""
            src = c.source or c.name
            if row.get('source') != src:
                return False
            if (c.medium or 'custom') != row.get('medium'):
                return False
            for fname in ('campaign', 'content', 'term', 'source_platform'):
                cv = getattr(c, fname)
                if cv and row.get(fname) != cv:
                    return False
            return True

        def _user_row_matches(row, c):
            src = c.source or c.name
            if row.get('source') != src:
                return False
            if c.medium and row.get('medium') != c.medium:
                return False
            if c.campaign and row.get('campaign') != c.campaign:
                return False
            return True

        breakdown = []
        active_today = 0
        for c in campaigns:
            c_visits = 0
            c_today = 0
            for r in visit_rows:
                if _row_matches(r, c):
                    c_visits += r['visits']
                    c_today += r['today_visits']

            c_users = sum(r['n'] for r in user_rows if _user_row_matches(r, c))

            if c_today > 0:
                active_today += 1

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
                "created_at": c.created_at,
            })

        total_traffic = sum(r['visits'] for r in visit_rows)

        return Response({
            "total_sources": total_sources,
            "total_traffic": total_traffic,
            "active_today": active_today,
            "campaigns": breakdown,
        })

class LogVisitView(APIView):
    """
    Public ingest endpoint. We DO NOT call record_visit synchronously anymore —
    that opens a Postgres connection on the request thread. Instead we enqueue
    a Celery task so worker concurrency caps the DB pressure.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'analytics_ingest'

    def post(self, request):
        from .tasks import record_visit_task
        from .redis_tracking import incr_visit_counter, mark_seen

        path = request.data.get('path', '')
        if not path:
            return Response({"status": "ignored"})

        vuid = (request.data.get('visitor_id')
                or getattr(request, 'vuid', None)
                or request.COOKIES.get('vux_id'))
        user = getattr(request, 'user', None)
        user_id = user.id if user and user.is_authenticated else None

        # Always count; only persist on the first sighting of the day.
        incr_visit_counter(authenticated=bool(user_id))
        if mark_seen(vuid or 'anon', user_id=user_id):
            record_visit_task.delay({
                "path": path,
                "visitor_id": vuid,
                "user_id": user_id,
                "is_bot": False,
                "attribution": request.data.get('attribution') or {},
                "referrer": request.data.get('referrer'),
            })

        return Response({"status": "ok"})

class AnalyticsDashboardView(APIView):
    permission_classes = [IsAdminUser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'admin_read'

    def get(self, request):
        start_datetime, end_datetime, range_label, days = get_admin_date_range(
            days_param=request.GET.get('days'),
            date_str=request.GET.get('date')
        )
        start_date = start_datetime.date()

        # Real-time: Online Now (last 5 minutes via Presence Cache)
        presence_data = cache.get(ONLINE_SET_KEY, {})
        online_now = len(presence_data) if isinstance(presence_data, dict) else 0

        visit_queryset = VisitorLog.objects.filter(
            timestamp__range=(start_datetime, end_datetime),
            is_bot=False
        )

        # Revenue is defined as Deposits (Money coming in)
        revenue_transactions = Transaction.objects.filter(
            created_at__range=(start_datetime, end_datetime),
            type=Transaction.Type.DEPOSIT,
            status=Transaction.Status.COMPLETED,
        )

        # Spending is defined as Payments (Money used by users)
        spending_transactions = Transaction.objects.filter(
            created_at__range=(start_datetime, end_datetime),
            type=Transaction.Type.PAYMENT,
            status=Transaction.Status.COMPLETED,
        )

        from django.db.models.functions import Cast, Coalesce
        from django.db.models import CharField

        # 1. Visitor Stats (Daily)
        # We use a combined ID (User ID or Visitor ID) to ensure authenticated users 
        # are counted as 1 unique visitor even if their persistent ID changes.
        
        source_filter = request.query_params.get('source')
        medium_filter = request.query_params.get('medium')
        campaign_filter = request.query_params.get('campaign')

        if source_filter:
            visit_queryset = visit_queryset.filter(source=source_filter)
        if medium_filter:
            visit_queryset = visit_queryset.filter(medium=medium_filter)
        if campaign_filter:
            visit_queryset = visit_queryset.filter(campaign=campaign_filter)

        visitor_stats = visit_queryset.annotate(
            date=TruncDate('timestamp'),
            combined_id=Coalesce(Cast('user_id', CharField()), 'visitor_id')
        ).values('date').annotate(
            total_visits=Count('id'),
            unique_visitors=Count('combined_id', distinct=True)
        ).order_by('date')

        # 2. Wallet Stats (Daily)
        inflow_stats = revenue_transactions.annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            total_sales=Count('id'),
            total_revenue=Sum('amount')
        ).order_by('date')

        outflow_stats = spending_transactions.annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            total_spending=Sum('amount')
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

        for item in inflow_stats:
            d = str(item['date'])
            if d in stats_map:
                stats_map[d]['total_sales'] = item['total_sales']
                stats_map[d]['total_revenue'] = float(item['total_revenue'] or 0)

        for item in outflow_stats:
            d = str(item['date'])
            if d in stats_map:
                # Add spending to the map if we want to track it in charts too
                stats_map[d]['total_spending'] = abs(float(item['total_spending'] or 0))

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


        revenue_summary = revenue_transactions.aggregate(
            total_sales=Count('id'),
            total_revenue=Sum('amount'),
        )

        spending_summary = spending_transactions.aggregate(
            total_spending=Sum('amount'),
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
        sales_count = revenue_summary['total_sales'] or 0

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
                "total_sales": revenue_summary['total_sales'] or 0,
                "total_revenue": float(revenue_summary['total_revenue'] or 0),
                "total_spending": abs(float(spending_summary['total_spending'] or 0)),
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
