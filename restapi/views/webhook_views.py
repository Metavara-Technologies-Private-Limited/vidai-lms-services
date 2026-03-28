# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import logging
import traceback

from django.conf import settings

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from restapi.models import Lead, Clinic
from restapi.services.zapier_service import send_to_zapier

from drf_yasg.utils import swagger_auto_schema

from django.db import transaction

from rest_framework.exceptions import ValidationError

from restapi.serializers.mailchimp_serializer import MailchimpWebhookSerializer
from restapi.services.mailchimp_service import create_mailchimp_event

logger = logging.getLogger(__name__)


# =====================================================
# GOHIGHLEVEL WEBHOOK — Receives leads from Zapier LeadConnector
# POST /api/webhooks/gohighlevel/lead/
# =====================================================
class GoHighLevelLeadWebhookAPIView(APIView):
    def post(self, request):
        try:
            data = request.data
            print("GHL Webhook received:", data)

            # ── Extract name fields ──────────────────────────────────────
            first_name = data.get('first_name') or data.get('contact_first_name') or ""
            last_name  = data.get('last_name')  or data.get('contact_last_name')  or ""
            full_name  = f"{first_name} {last_name}".strip()

            if not full_name:
                full_name = (
                    data.get("contact_name") or
                    data.get("name") or
                    data.get("full_name") or
                    data.get("contact_full_name") or
                    "GHL Lead"
                )

            # ── Extract contact fields ───────────────────────────────────
            email = (
                data.get("email") or
                data.get("contact_email") or ""
            )
            phone = (
                data.get("phone") or
                data.get("phone_number") or
                data.get("contact_phone") or ""
            )

            # ── Extract location ─────────────────────────────────────────
            location = (
                data.get("city") or
                data.get("state") or
                data.get("country") or
                data.get("address1") or ""
            )

            # ── Truncate fields to fit DB column limits ──────────────────
            full_name = (full_name or "GHL Lead")[:255]
            email     = email[:254]
            phone     = phone[:20]
            location  = location[:255]

            # ── Get clinic ───────────────────────────────────────────────
            clinic = Clinic.objects.first()
            if not clinic:
                return Response(
                    {"error": "No clinic found"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # ── Get first department (required field in Lead model) ───────
            from restapi.models import Department
            department = Department.objects.filter(clinic=clinic).first()
            if not department:
                return Response(
                    {"error": "No department found for clinic"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # ── Create lead ──────────────────────────────────────────────
            lead = Lead.objects.create(
                clinic=clinic,
                department=department,
                full_name=full_name,
                email=email,
                contact_no=phone,
                lead_status="new",
                source="facebook",
                location=location,
                is_active=True,
            )

            # ── Notify Zapier ────────────────────────────────────────────
            send_to_zapier({
                "event":       "lead_created",
                "lead_id":     str(lead.id),
                "clinic_id":   lead.clinic.id,
                "full_name":   lead.full_name,
                "contact_no":  lead.contact_no,
                "email":       lead.email,
                "lead_status": lead.lead_status,
                "source":      "facebook",
                "location":    location,
            })

            logger.info(f"[GHL Webhook] Lead created: {lead.id} | {full_name}")

            return Response(
                {
                    "status":   "lead_created",
                    "lead_id":  str(lead.id),
                    "name":     full_name,
                    "source":   "facebook",
                    "location": location,
                },
                status=status.HTTP_201_CREATED
            )

        except Exception:
            logger.error("GHL Webhook Error:\n" + traceback.format_exc())
            print("GHL Webhook Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# -------------------------------------------------------------------
# Mailchimp Webhook Receiver API View (POST)
# -------------------------------------------------------------------
class MailchimpWebhookAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Mailchimp Webhook Receiver",
        request_body=MailchimpWebhookSerializer,
        responses={
            200: "Mailchimp Event Stored Successfully",
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Mailchimp"],
    )
    @transaction.atomic
    def post(self, request):
        try:
            serializer = MailchimpWebhookSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            create_mailchimp_event(validated_data)

            return Response(
                {"message": "Mailchimp event stored successfully"},
                status=status.HTTP_200_OK,
            )

        except ValidationError as e:
            return Response(
                e.detail,
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Mailchimp Webhook Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

