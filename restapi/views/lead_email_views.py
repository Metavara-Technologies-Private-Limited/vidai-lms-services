# =====================================================
# Imports
# =====================================================
import logging
import traceback

from django.db import transaction

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
# Lead Email API View (CREATE + OPTIONAL SEND)
# =====================================================
class LeadEmailAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Create Lead Email (Optional: Send Immediately)",
        operation_description="""
        Create an email record for a lead.

        If `send_now=true`, the email will be sent immediately.
        Otherwise, it will be saved as DRAFT.
        """,
        request_body=LeadEmailSerializer,
        responses={
            201: openapi.Response(
                description="Email created (and optionally sent)",
                schema=LeadEmailSerializer
            ),
            400: "Bad Request"
        },
        tags=["Lead Email"]
    )
    @transaction.atomic
    def post(self, request):

        try:
            serializer = LeadEmailSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # ✅ Get validated send_now
            send_now = serializer.validated_data.get("send_now", False)

            # ✅ Create email (clinic auto-handled in model)
            email_obj = serializer.save()

            # ✅ Send immediately if requested
            if send_now:
                email_obj = send_lead_email(email_obj.id)

                return Response(
                    {
                        "message": "Email created and sent successfully",
                        "status": email_obj.status,
                        "sent_at": email_obj.sent_at,
                        "data": LeadEmailSerializer(email_obj).data
                    },
                    status=status.HTTP_201_CREATED
                )

            # ✅ Default response (draft)
            return Response(
                {
                    "message": "Email saved as draft",
                    "status": email_obj.status,
                    "data": LeadEmailSerializer(email_obj).data
                },
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            logger.error("Lead Email Create Error:\n" + traceback.format_exc())

            return Response(
                {
                    "error": "Email creation failed",
                    "details": str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )


# =====================================================
# Lead Email List API View
# =====================================================
class LeadMailListAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Get Lead Emails",
        operation_description="""
        Retrieve list of emails.

        Optional Filters:
        - lead_uuid
        - clinic_id
        """,
        manual_parameters=[
            openapi.Parameter(
                "lead_uuid",
                openapi.IN_QUERY,
                description="Filter by Lead UUID",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "clinic_id",
                openapi.IN_QUERY,
                description="Filter by Clinic ID",
                type=openapi.TYPE_STRING,
                required=False,
            ),
        ],
        responses={200: LeadMailListSerializer(many=True)},
        tags=["Lead Email"]
    )
    def get(self, request):

        try:
            lead_uuid = request.query_params.get("lead_uuid")
            clinic_id = request.query_params.get("clinic_id")

            queryset = LeadEmail.objects.all().order_by("-created_at")

            # ✅ Filter by lead
            if lead_uuid:
                queryset = queryset.filter(lead__id=lead_uuid)

            # ✅ Filter by clinic
            if clinic_id:
                queryset = queryset.filter(clinic__id=clinic_id)

            serializer = LeadMailListSerializer(queryset, many=True)

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Lead Mail Fetch Error:\n" + traceback.format_exc())

            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )