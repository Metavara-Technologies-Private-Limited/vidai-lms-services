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


def _filter_user_leads(queryset, user):
    if not hasattr(user, "profile") or not user.profile.role:
        return queryset.none()

    role_name = (user.profile.role.name or "").strip().lower()

    # Super admin/admin → full clinic access
    if role_name in ["super admin", "superadmin", "admin"]:
        return queryset

    return queryset.filter(
        Q(lead__assigned_to_id=user.id)
        | Q(lead__created_by_id=user.id)
        | Q(lead__personal_id=user.id)
    )

class InteractionCountsAPIView(APIView):
    """
    GET /api/interactions/counts/?clinic_id=25

    Returns per-platform interaction counts for the Communication chart.
    """

    def get(self, request):
        try:
            clinic_id = request.query_params.get("clinic_id")

            if not clinic_id:
                return Response(
                    {"error": "clinic_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # ───────────────── EMAIL ─────────────────
            email_qs = _filter_user_leads(
                LeadEmail.objects.filter(lead__clinic_id=clinic_id), request.user
            )

            email_counts = email_qs.aggregate(
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

            # ───────────────── SMS ─────────────────
            sms_qs = _filter_user_leads(
                TwilioMessage.objects.filter(lead__clinic_id=clinic_id), request.user
            )

            sms_counts = sms_qs.aggregate(
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

            # ───────────────── CALL ─────────────────
            call_qs = _filter_user_leads(
                TwilioCall.objects.filter(lead__clinic_id=clinic_id),
                request.user
            )

            call_high = 0
            call_low = 0
            call_no = 0

            for call in call_qs:
                status_value = (call.status or "").lower()

                raw_payload = (
                    call.raw_payload
                    if isinstance(call.raw_payload, dict)
                    else {}
             )
                duration = int(raw_payload.get("call_duration", 0) or 0)

                answered_by = (raw_payload.get("answered_by", "") or "").lower()

                if (status_value == "completed" and duration >= 10):

                    call_high += 1

                elif (
                    status_value in ["busy", "no-answer", "no_answer", "canceled"]
                    or (status_value == "completed"
                    and duration > 0
                    and duration <10
                )
                    or answered_by in ["machine_start", "fax"]
                ):
                    call_low += 1

                elif status_value in ["failed"]:
                    call_no += 1

            # ───────────────── FINAL RESPONSE ─────────────────
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
