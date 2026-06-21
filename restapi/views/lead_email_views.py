import logging
import traceback

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from restapi.models import LeadEmail
from restapi.serializers.lead_email_serializer import (
    LeadEmailSerializer,
    LeadMailListSerializer
)
from restapi.services.lead_email_service import send_lead_email

logger = logging.getLogger(__name__)


# =====================================================
# CREATE + SEND EMAIL
# =====================================================
class LeadEmailAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Create Lead Email (Optional Send)",
        request_body=LeadEmailSerializer,
        tags=["Lead Email"]
    )
    @transaction.atomic
    def post(self, request):

        try:
            serializer = LeadEmailSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            email_obj = serializer.save()

            # ✅ FIX BOOLEAN (VERY IMPORTANT)
            send_now = str(request.data.get("send_now", "false")).lower() == "true"

            if send_now:
                email_obj = send_lead_email(email_obj.id)

                return Response(
                    {
                        "message": "Email sent successfully",
                        "status": email_obj.status,
                        "sent_at": email_obj.sent_at,
                        "clinic_id": email_obj.clinic.id if email_obj.clinic else None,
                        "data": LeadEmailSerializer(email_obj).data
                    },
                    status=status.HTTP_201_CREATED
                )

            return Response(
                {
                    "message": "Email saved as draft",
                    "status": email_obj.status,
                    "clinic_id": email_obj.clinic.id if email_obj.clinic else None,
                    "data": LeadEmailSerializer(email_obj).data
                },
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            logger.error("Lead Email Error:\n" + traceback.format_exc())

            return Response(
                {
                    "error": "Email failed",
                    "details": str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )


# =====================================================
# LIST EMAILS (WITH clinic_id FILTER)
# =====================================================
class LeadMailListAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Get Emails",
        manual_parameters=[
            openapi.Parameter("lead_uuid", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("clinic_id", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
        tags=["Lead Email"]
    )
    def get(self, request):

        try:
            lead_uuid = request.query_params.get("lead_uuid")
            clinic_id = request.query_params.get("clinic_id")

            queryset = LeadEmail.objects.all().order_by("-created_at")

            if lead_uuid:
                queryset = queryset.filter(lead__id=lead_uuid)

            if clinic_id:
                queryset = queryset.filter(clinic__id=clinic_id)

            serializer = LeadMailListSerializer(queryset, many=True)

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Email Fetch Error:\n" + traceback.format_exc())

            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================
# ✅ NEW: INBOUND EMAIL WEBHOOK (from Zapier)
# When lead replies to email → Zapier POSTs here
# POST /api/lead-email/inbound/
# No auth required — called by Zapier
# =====================================================
@method_decorator(csrf_exempt, name="dispatch")
class LeadEmailInboundWebhookAPIView(APIView):

    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(auto_schema=None)
    def post(self, request):
        try:
            data = request.data

            from_email = data.get("from_email", "") or data.get("from", "")
            subject    = data.get("subject", "Re: (no subject)")
            body       = data.get("body", "") or data.get("message", "")
            to_email   = data.get("to_email", "") or data.get("to", "")

            logger.info(
                "LeadEmailInbound: from=%s to=%s subject=%s",
                from_email, to_email, subject,
            )

            if not from_email or not body:
                return Response(
                    {"error": "from_email and body are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ── Find lead by email ────────────────────────────────────────
            from restapi.models.lead import Lead

            lead = Lead.objects.filter(
                email__iexact=from_email.strip()
            ).first()

            if not lead:
                logger.warning(
                    "LeadEmailInbound: no lead found for email=%s", from_email
                )
                # Return 200 so Zapier does not retry
                return Response(
                    {"message": "No lead found for this email, skipped"},
                    status=status.HTTP_200_OK,
                )

            # ── Save reply to LeadEmail table ─────────────────────────────
            LeadEmail.objects.create(
                lead         = lead,
                clinic       = getattr(lead, "clinic", None),
                subject      = subject,
                email_body   = body,
                sender_email = from_email,
                status       = "RECEIVED",
                sent_at      = None,
            )

            logger.info(
                "LeadEmailInbound: saved reply from lead=%s email=%s",
                str(lead.id), from_email,
            )

            return Response(
                {"message": "Reply saved successfully"},
                status=status.HTTP_200_OK,
            )

        except Exception:
            logger.error("LeadEmailInbound error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )