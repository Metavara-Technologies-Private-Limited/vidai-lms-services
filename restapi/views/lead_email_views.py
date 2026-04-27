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