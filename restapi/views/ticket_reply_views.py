# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import logging
import traceback

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from restapi.models import Ticket, Employee
from restapi.serializers.ticket_serializer import (
    TicketReplySerializer,
    TicketReplyWriteSerializer,
)

from restapi.services.ticket_service import send_ticket_reply_service
from restapi.utils.permissions import has_action_permission_for_labels

logger = logging.getLogger(__name__)


def _has_tickets_permission(user, action: str) -> bool:
    return has_action_permission_for_labels(
        user,
        action,
        ["tickets", "ticket", "ticket management", "ticket_management"],
    )


def _ticket_permission_denied(action: str):
    return Response(
        {
            "success": False,
            "message": f"Permission denied: tickets {action}",
        },
        status=status.HTTP_403_FORBIDDEN,
    )


class TicketReplyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Send an email reply for a ticket with optional CC and BCC",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["subject", "message", "to"],
            properties={
                "subject": openapi.Schema(type=openapi.TYPE_STRING),
                "message": openapi.Schema(type=openapi.TYPE_STRING),
                "to": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL
                    ),
                ),
                "cc": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL
                    ),
                ),
                "bcc": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL
                    ),
                ),
                "sent_by": openapi.Schema(
                    type=openapi.TYPE_INTEGER, description="Employee ID"
                ),
            },
        ),
        responses={
            201: TicketReplySerializer,
            400: "Validation Error",
            404: "Ticket Not Found",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def post(self, request, ticket_id):
        if not _has_tickets_permission(request.user, "add"):
            return _ticket_permission_denied("add")

        try:
            ticket = Ticket.objects.filter(
                id=ticket_id,
                is_deleted=False,
            ).first()

            if not ticket:
                return Response(
                    {"error": "Ticket not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = TicketReplyWriteSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            sent_by = None
            sent_by_id = data.get("sent_by")
            if sent_by_id:
                sent_by = Employee.objects.filter(id=sent_by_id).first()

            reply = send_ticket_reply_service(
                ticket=ticket,
                subject=data["subject"],
                message=data["message"],
                to_emails=data["to"],
                cc_emails=data.get("cc", []),
                bcc_emails=data.get("bcc", []),
                sent_by=sent_by,
            )

            return Response(
                TicketReplySerializer(reply).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as validation_error:
            logger.warning(f"Ticket Reply validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Ticket Reply API Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )



