# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import logging
import traceback

from django.core.cache import cache

from restapi.models import Lead

from django.db.models import Count

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from restapi.models import TwilioCall, TwilioMessage
logger = logging.getLogger(__name__)
# =====================================================
# DEBUG API — Temporary: check what Twilio statuses are in DB
# GET /api/debug/twilio-status/
# Remove this endpoint once you've confirmed the status values.
# =====================================================
class TwilioDebugAPIView(APIView):
    """
    GET /api/debug/twilio-status/
    Shows all status values stored in TwilioCall and TwilioMessage tables.
    Use this to confirm what statuses Twilio is saving so we can map them correctly.
    Remove after debugging.
    """
    def get(self, request):
        from django.db.models import Count

        call_statuses = (
            TwilioCall.objects
            .values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        sms_statuses = (
            TwilioMessage.objects
            .values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        return Response({
            "total_calls":    TwilioCall.objects.count(),
            "total_messages": TwilioMessage.objects.count(),
            "call_statuses":  list(call_statuses),
            "sms_statuses":   list(sms_statuses),
        }, status=status.HTTP_200_OK)


# =====================================================
# MAIL INSIGHTS DEBUG API — Temporary diagnostic tool
# GET /api/debug/mail-insights-log/
# Open in browser to see if Zapier is hitting Django.
# Remove after confirming flow works end-to-end.
# =====================================================
class MailInsightsDebugAPIView(APIView):
    """
    GET /api/debug/mail-insights-log/
    Shows current cache state + DB lead counts.
    Use this to verify Zapier is actually posting to your endpoint.
    """

    def get(self, request):
        try:
            cached = cache.get("mail_insights")

            appointments_in_db = Lead.objects.filter(
                is_deleted=False,
                lead_status__icontains="appointment"
            ).count()

            all_leads_in_db = Lead.objects.filter(is_deleted=False).count()

            recent_statuses = list(
                Lead.objects.filter(is_deleted=False)
                .order_by("-created_at")
                .values("full_name", "lead_status", "created_at")[:5]
            )

            return Response({
                "cache_state": cached or "EMPTY — Zapier has not posted yet (or cache was cleared)",
                "db_counts": {
                    "total_leads":       all_leads_in_db,
                    "appointment_leads": appointments_in_db,
                },
                "recent_lead_statuses": recent_statuses,
                "instructions": {
                    "appointment_zap_body": {"appointments_booked": 1},
                    "lead_created_zap_body": {"leads_created": 1},
                    "zapier_must_post_to": "http://YOUR_PUBLIC_IP:8000/api/mail-insights/",
                    "note": "Zapier cannot reach localhost — use ngrok or public IP",
                },
            }, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Mail Insights Debug Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)