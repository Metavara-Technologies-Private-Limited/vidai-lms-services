# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import logging
import traceback

from django.db.models import Count, Q

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from restapi.models import LeadEmail, TwilioMessage, TwilioCall

logger = logging.getLogger(__name__)


# =====================================================
# INTERACTION COUNTS API
# GET /api/interactions/counts/
# Feeds the CommunicationChart with REAL data from:
#   Email    → Zapier cache  (mail_insights)
#   SMS      → TwilioMessage DB
#   Call     → TwilioCall    DB
#   WhatsApp → 0  (future scope)
#   Chatbot  → 0  (future scope)
#
# Engagement mapping:
#   Email:  appointments_booked → high | leads_created → low | 0 → no
#   SMS:    delivered/sent → high | failed/undelivered → low | queued/accepted → no
#   Call:   completed/in-progress/ringing → high | busy/no-answer → low | failed/canceled → no
#           Fallback: if no status matches but records exist → all go to high
# =====================================================
class InteractionCountsAPIView(APIView):
    """
    GET /api/interactions/counts/

    Returns per-platform interaction counts for the Communication chart.
    Order: Email → SMS → Call → WhatsApp → Chatbot
    """

    def get(self, request):
        try:
            # ── EMAIL — from LeadEmail DB ────────────────────────────────
            email_counts = LeadEmail.objects.aggregate(
                high=Count(
                    "id",
                    filter=Q(
                        status=LeadEmail.StatusChoices.SENT,
                        sent_at__isnull=False
                    )
                ),
                low=Count(
                    "id",
                    filter=Q(status=LeadEmail.StatusChoices.FAILED)
                ),
                no=Count(
                    "id",
                    filter=Q(
                        status__in=[
                            LeadEmail.StatusChoices.DRAFT,
                            LeadEmail.StatusChoices.SCHEDULED
                        ]
                    )
                )
            )

            email_high = email_counts["high"] or 0
            email_low  = email_counts["low"] or 0
            email_no   = email_counts["no"] or 0


            # ── SMS — from TwilioMessage DB ──────────────────────────────
            sms_counts = TwilioMessage.objects.aggregate(
                high=Count(
                    "id",
                    filter=Q(status__in=["delivered", "sent", "queued_via_zapier"])
                ),
                low=Count(
                    "id",
                    filter=Q(status__in=["failed", "undelivered"])
                ),
                no=Count(
                    "id",
                    filter=Q(status__in=["queued", "accepted", "sending", "receiving", "received"])
                )
            )

            sms_high = sms_counts["high"] or 0
            sms_low  = sms_counts["low"] or 0
            sms_no   = sms_counts["no"] or 0


            # ── CALLS — from TwilioCall DB ───────────────────────────────
            call_counts = TwilioCall.objects.aggregate(
                high=Count(
                    "id",
                    filter=Q(status__in=["completed", "in-progress", "ringing", "in_progress"])
                ),
                low=Count(
                    "id",
                    filter=Q(status__in=["busy", "no-answer", "no_answer"])
                ),
                no=Count(
                    "id",
                    filter=Q(status__in=["failed", "canceled"])
                )
            )

            call_high = call_counts["high"] or 0
            call_low  = call_counts["low"] or 0
            call_no   = call_counts["no"] or 0

            # Fallback: if no categorized calls but records exist
            total_calls = TwilioCall.objects.count()
            if call_high == 0 and call_low == 0 and call_no == 0 and total_calls > 0:
                call_high = total_calls


            # ── FINAL RESPONSE ──────────────────────────────────────────
            data = [
                {"platform": "Email",    "high": email_high, "low": email_low, "no": email_no},
                {"platform": "SMS",      "high": sms_high,   "low": sms_low,   "no": sms_no},
                {"platform": "Call",     "high": call_high,  "low": call_low,  "no": call_no},
                {"platform": "WhatsApp", "high": 0,          "low": 0,         "no": 0},
                {"platform": "Chatbot",  "high": 0,          "low": 0,         "no": 0},
            ]

            return Response(data, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Interaction Counts Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )