from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from wallet.models import WithdrawalRequest


def _serialize(req: WithdrawalRequest) -> dict:
    return {
        "id": str(req.id),
        "user": {
            "id": req.user.id,
            "username": req.user.username,
            "email": req.user.email,
        },
        "amount": float(req.amount),
        "usdt_address": req.usdt_address,
        "status": req.status,
        "requestedAt": req.created_at.isoformat(),
        "updatedAt": req.updated_at.isoformat(),
    }


class PayoutListView(APIView):
    """List referral payout (withdrawal) requests for admin."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        status_filter = request.GET.get("status", "pending").strip().lower()
        search = request.GET.get("search", "").strip()
        page_size = int(request.GET.get("page_size", 20))

        qs = WithdrawalRequest.objects.select_related("user").all()

        if status_filter in {
            WithdrawalRequest.Status.PENDING,
            WithdrawalRequest.Status.COMPLETED,
            WithdrawalRequest.Status.REJECTED,
        }:
            qs = qs.filter(status=status_filter)
        elif status_filter == "all":
            pass
        else:
            qs = qs.filter(status=WithdrawalRequest.Status.PENDING)

        if search:
            qs = qs.filter(
                Q(user__username__icontains=search)
                | Q(user__email__icontains=search)
                | Q(usdt_address__icontains=search)
            )

        qs = qs.order_by("-created_at")

        paginator = PageNumberPagination()
        paginator.page_size = page_size
        page = paginator.paginate_queryset(qs, request)

        totals = WithdrawalRequest.objects.aggregate(
            pending_count=Sum(
                "amount",
                filter=Q(status=WithdrawalRequest.Status.PENDING),
            ),
            paid_total=Sum(
                "amount",
                filter=Q(status=WithdrawalRequest.Status.COMPLETED),
            ),
        )
        stats = {
            "pending_count": WithdrawalRequest.objects.filter(
                status=WithdrawalRequest.Status.PENDING
            ).count(),
            "pending_amount": float(totals["pending_count"] or 0),
            "paid_total": float(totals["paid_total"] or 0),
            "rejected_count": WithdrawalRequest.objects.filter(
                status=WithdrawalRequest.Status.REJECTED
            ).count(),
        }

        return Response(
            {
                "results": [_serialize(r) for r in page],
                "count": paginator.page.paginator.count,
                "current_page": paginator.page.number,
                "total_pages": paginator.page.paginator.num_pages,
                "stats": stats,
                "filters": {"status": status_filter, "search": search},
            }
        )


class PayoutApproveView(APIView):
    """Mark a payout request as completed (paid)."""

    permission_classes = [IsAdminUser]

    def post(self, request):
        request_id = request.data.get("requestId")
        if not request_id:
            return Response(
                {"detail": "requestId required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            req = WithdrawalRequest.objects.select_related("user").get(id=request_id)
        except WithdrawalRequest.DoesNotExist:
            return Response(
                {"detail": "Payout request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if req.status != WithdrawalRequest.Status.PENDING:
            return Response(
                {"detail": f"Request is already {req.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            req.status = WithdrawalRequest.Status.COMPLETED
            req.save(update_fields=["status", "updated_at"])

        return Response({"detail": "Payout marked as completed.", "request": _serialize(req)})


class PayoutRejectView(APIView):
    """Reject a payout request.

    The user's referral balance was debited when they submitted the request
    (see api/views/referrals.py:request_withdrawal). Rejection MUST decide
    what happens to that held amount — see handle_rejection() below.
    """

    permission_classes = [IsAdminUser]

    def post(self, request):
        request_id = request.data.get("requestId")
        reason = (request.data.get("reason") or "").strip()

        if not request_id:
            return Response(
                {"detail": "requestId required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            req = WithdrawalRequest.objects.select_related("user__wallet").get(id=request_id)
        except WithdrawalRequest.DoesNotExist:
            return Response(
                {"detail": "Payout request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if req.status != WithdrawalRequest.Status.PENDING:
            return Response(
                {"detail": f"Request is already {req.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            self.handle_rejection(req, reason)
            req.status = WithdrawalRequest.Status.REJECTED
            req.save(update_fields=["status", "updated_at"])

        return Response({"detail": "Payout rejected.", "request": _serialize(req)})

    def handle_rejection(self, req: WithdrawalRequest, reason: str) -> None:
        """Decide what happens to the user's held referral balance on rejection.

        The amount in `req.amount` was already deducted from `req.user.wallet.referral_balance`
        when the request was submitted. Options:

          (a) Auto-refund: credit `req.amount` back to `req.user.wallet.referral_balance`.
              Pros: best UX, no manual ops. Cons: a bad-actor user could spam requests.

          (b) Keep funds held / forfeit on reject: do nothing here. User must contact
              support. Pros: deters abuse. Cons: looks like theft if rejection is for
              admin-side reasons (typo'd address etc.).

          (c) Refund only if `reason` matches a whitelist (e.g. "wrong_address"),
              forfeit if it matches a fraud reason. Middle ground.

        TODO(user): implement the policy below.
        """
        raise NotImplementedError(
            "handle_rejection: implement refund policy in api/views/payouts.py"
        )
