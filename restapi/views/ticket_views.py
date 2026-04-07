# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import logging
import traceback

from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from restapi.models import Ticket, Employee, TicketTimeline, Document
from restapi.serializers.ticket_serializer import (
    TicketWriteSerializer,
    TicketDetailSerializer,
    TicketListSerializer,
)
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


# -------------------------------------------------------------------
# Ticket Create API View (POST)
# -------------------------------------------------------------------
class TicketCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Create a new support ticket",
        request_body=TicketWriteSerializer,
        responses={
            201: TicketDetailSerializer,
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def post(self, request):
        if not _has_tickets_permission(request.user, "add"):
            return _ticket_permission_denied("add")

        try:
            serializer = TicketWriteSerializer(
                data=request.data,
                context={"request": request},
            )

            serializer.is_valid(raise_exception=True)

            ticket = serializer.save()

            return Response(
                TicketDetailSerializer(ticket).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as validation_error:
            logger.warning(f"Ticket creation validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Ticket Create API Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Ticket Update API View (PUT)
# -------------------------------------------------------------------
class TicketUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Update an existing ticket (Full Update)",
        request_body=TicketWriteSerializer,
        responses={
            200: TicketDetailSerializer,
            400: "Validation Error",
            404: "Ticket Not Found",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def put(self, request, ticket_id):
        if not _has_tickets_permission(request.user, "edit"):
            return _ticket_permission_denied("edit")

        try:
            ticket = Ticket.objects.filter(
                id=ticket_id,
                is_deleted=False
            ).first()

            if not ticket:
                return Response(
                    {"error": "Ticket not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = TicketWriteSerializer(
                ticket,
                data=request.data,
                context={"request": request},
            )

            serializer.is_valid(raise_exception=True)

            updated_ticket = serializer.save()

            return Response(
                TicketDetailSerializer(updated_ticket).data,
                status=status.HTTP_200_OK,
            )

        except ValidationError as validation_error:
            logger.warning(f"Ticket update validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Ticket Update API Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Ticket List API View (GET)
# -------------------------------------------------------------------
class TicketListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Retrieve paginated list of tickets with optional filters",
        manual_parameters=[
            openapi.Parameter("status", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("priority", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("lab_id", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("department_id", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("from_date", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("to_date", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("page_size", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
        ],
        responses={
            200: TicketListSerializer(many=True),
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def get(self, request):
        if not _has_tickets_permission(request.user, "view"):
            return _ticket_permission_denied("view")

        try:
            queryset = Ticket.objects.filter(is_deleted=False)

            if request.query_params.get("status"):
                queryset = queryset.filter(status=request.query_params.get("status"))

            if request.query_params.get("priority"):
                queryset = queryset.filter(priority=request.query_params.get("priority"))

            if request.query_params.get("lab_id"):
                queryset = queryset.filter(lab_id=request.query_params.get("lab_id"))

            if request.query_params.get("department_id"):
                queryset = queryset.filter(department_id=request.query_params.get("department_id"))

            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 10))
            start = (page - 1) * page_size
            end = start + page_size

            total_count = queryset.count()
            paginated_queryset = queryset[start:end]

            serializer = TicketListSerializer(paginated_queryset, many=True)

            return Response(
                {
                    "count": total_count,
                    "current_page": page,
                    "results": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception:
            logger.error("Ticket List API Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Ticket Detail API View (GET)
# -------------------------------------------------------------------
class TicketDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Retrieve detailed information of a specific ticket",
        responses={
            200: TicketDetailSerializer,
            404: "Ticket Not Found",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def get(self, request, ticket_id):
        if not _has_tickets_permission(request.user, "view"):
            return _ticket_permission_denied("view")

        if getattr(self, "swagger_fake_view", False):
            return Response(status=200)

        try:
            ticket = Ticket.objects.filter(
                id=ticket_id,
                is_deleted=False
            ).first()

            if not ticket:
                return Response(
                    {"error": "Ticket not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = TicketDetailSerializer(ticket)

            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )

        except Exception:
            logger.error("Ticket Detail API Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Ticket Assign for Employee API View (POST)
# -------------------------------------------------------------------
class TicketAssignAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Assign a ticket to an employee",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["assigned_to_id"],
            properties={
                "assigned_to_id": openapi.Schema(type=openapi.TYPE_STRING)
            },
        ),
        responses={
            200: TicketDetailSerializer,
            400: "Validation Error",
            404: "Ticket Not Found",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def post(self, request, ticket_id):
        if not _has_tickets_permission(request.user, "edit"):
            return _ticket_permission_denied("edit")

        try:
            ticket = Ticket.objects.filter(
                id=ticket_id,
                is_deleted=False
            ).first()

            if not ticket:
                return Response(
                    {"error": "Ticket not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            assigned_to_id = request.data.get("assigned_to_id")
            assigned_to_name_raw = request.data.get("assigned_to_name")

            if not assigned_to_id:
                raise ValidationError("assigned_to_id is required")

            assigned_employee = Employee.objects.filter(id=assigned_to_id).first()
            assigned_to_name = (
                assigned_employee.emp_name
                if assigned_employee
                else str(assigned_to_name_raw).strip()
                if assigned_to_name_raw is not None
                else f"User {assigned_to_id}"
            )

            ticket.assigned_to_id = assigned_to_id
            ticket.assigned_to_name = assigned_to_name
            ticket.save()

            TicketTimeline.objects.create(
                ticket=ticket,
                action="Ticket Assigned",
                done_by_id=assigned_to_id,
                done_by_name=assigned_to_name,
            )

            return Response(
                TicketDetailSerializer(ticket).data,
                status=status.HTTP_200_OK,
            )

        except ValidationError as validation_error:
            logger.warning(f"Ticket Assign validation failed: {validation_error}")
            return Response(
                {"error": str(validation_error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Ticket Assign API Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Ticket Status Update API View (POST)
# -------------------------------------------------------------------
class TicketStatusUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Update the status of a ticket",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["status"],
            properties={
                "status": openapi.Schema(type=openapi.TYPE_STRING),
                "priority": openapi.Schema(type=openapi.TYPE_STRING),
                "assigned_to": openapi.Schema(type=openapi.TYPE_INTEGER),
                "assigned_to_name": openapi.Schema(type=openapi.TYPE_STRING),
                "type": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={
            200: TicketDetailSerializer,
            400: "Validation Error",
            404: "Ticket Not Found",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def post(self, request, ticket_id):
        if not _has_tickets_permission(request.user, "edit"):
            return _ticket_permission_denied("edit")

        try:
            ticket = Ticket.objects.filter(
                id=ticket_id,
                is_deleted=False
            ).first()

            if not ticket:
                return Response(
                    {"error": "Ticket not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # -------- OLD VALUES --------
            old_status = ticket.status
            old_priority = ticket.priority
            old_assigned = ticket.assigned_to_id
            old_assigned_name = ticket.assigned_to_name or "Unassigned"
            old_type = ticket.type

            # -------- REQUEST VALUES --------
            new_status = request.data.get("status")
            new_priority = request.data.get("priority")
            new_assigned = request.data.get("assigned_to")
            new_assigned_name_raw = request.data.get("assigned_to_name")
            new_type = request.data.get("type")
            has_assigned_field = "assigned_to" in request.data

            def resolve_assignee_name(assignee_id, fallback_name):
                if not assignee_id:
                    return None

                employee = Employee.objects.filter(id=assignee_id).first()
                if employee:
                    return employee.emp_name

                fallback = (
                    str(fallback_name).strip()
                    if fallback_name is not None
                    else ""
                )
                return fallback or f"User {assignee_id}"

            if not new_status:
                raise ValidationError("status field is required")

            # -------- UPDATE STATUS --------
            ticket.status = new_status

            if new_status == "resolved":
                ticket.resolved_at = timezone.now()

            if new_status == "closed":
                ticket.closed_at = timezone.now()

            # -------- UPDATE PRIORITY --------
            if new_priority:
                ticket.priority = new_priority

            # -------- UPDATE ASSIGN --------
            if has_assigned_field:
                normalized_assigned = (
                    None
                    if new_assigned in (None, "")
                    else int(new_assigned)
                )
                ticket.assigned_to_id = normalized_assigned
                ticket.assigned_to_name = resolve_assignee_name(
                    normalized_assigned,
                    new_assigned_name_raw,
                )

            # -------- UPDATE TYPE --------
            if new_type:
                ticket.type = new_type

            ticket.save()

            # -------- TIMELINE --------

            if old_status != new_status:
                TicketTimeline.objects.create(
                    ticket=ticket,
                    action=f"Status changed from {old_status} to {new_status}",
                    done_by_id=ticket.assigned_to_id,
                    done_by_name=ticket.assigned_to_name,
                )

            if new_priority and old_priority != new_priority:
                TicketTimeline.objects.create(
                    ticket=ticket,
                    action=f"Priority changed from {old_priority} to {new_priority}",
                    done_by_id=ticket.assigned_to_id,
                    done_by_name=ticket.assigned_to_name,
                )

            if new_type and old_type != new_type:
                TicketTimeline.objects.create(
                    ticket=ticket,
                    action=f"Type changed from {old_type} to {new_type}",
                    done_by_id=ticket.assigned_to_id,
                    done_by_name=ticket.assigned_to_name,
                )

            # -------- ASSIGN TIMELINE (SAFE FIX) --------
            if has_assigned_field:
                normalized_assigned = ticket.assigned_to_id
                if old_assigned != normalized_assigned:
                    new_user_name = ticket.assigned_to_name or "Unassigned"

                    TicketTimeline.objects.create(
                        ticket=ticket,
                        action=f"Assigned changed from {old_assigned_name} to {new_user_name}",
                        done_by_id=normalized_assigned,
                        done_by_name=new_user_name,
                    )

            return Response(
                TicketDetailSerializer(ticket).data,
                status=status.HTTP_200_OK,
            )

        except ValidationError as validation_error:
            logger.warning(f"Ticket Status validation failed: {validation_error}")
            return Response(
                {"error": str(validation_error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Ticket Status API Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
# -------------------------------------------------------------------
# Ticket Document Upload API View (POST)
# -------------------------------------------------------------------
class TicketDocumentUploadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Upload a document to a ticket",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["file"],
            properties={
                "file": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_BINARY
                )
            },
        ),
        responses={
            201: openapi.Schema(type=openapi.TYPE_OBJECT),
            400: "Validation Error",
            404: "Ticket Not Found",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def post(self, request, ticket_id):
        if not _has_tickets_permission(request.user, "edit"):
            return _ticket_permission_denied("edit")

        if getattr(self, "swagger_fake_view", False):
            return Response(status=200)

        try:
            ticket = Ticket.objects.filter(
                id=ticket_id,
                is_deleted=False
            ).first()

            if not ticket:
                return Response(
                    {"error": "Ticket not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            uploaded_file = request.FILES.get("file")

            if not uploaded_file:
                raise ValidationError("File is required")

            Document.objects.create(
                ticket=ticket,
                file=uploaded_file
            )

            return Response(
                TicketDetailSerializer(ticket).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as validation_error:
            logger.warning(
                f"Document Upload validation failed: {validation_error}"
            )
            return Response(
                {"error": str(validation_error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Document Upload API Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Ticket Delete API View (DELETE)
# -------------------------------------------------------------------
class TicketDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Soft delete a ticket",
        responses={
            200: "Ticket deleted successfully",
            404: "Ticket Not Found",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def delete(self, request, ticket_id):
        if not _has_tickets_permission(request.user, "print"):
            return _ticket_permission_denied("print")

        try:
            ticket = Ticket.objects.filter(
                id=ticket_id,
                is_deleted=False
            ).first()

            if not ticket:
                return Response(
                    {"error": "Ticket not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            ticket.is_deleted = True
            ticket.deleted_at = timezone.now()
            ticket.save()

            return Response(
                {"message": "Ticket deleted successfully"},
                status=status.HTTP_200_OK,
            )

        except Exception:
            logger.error("Ticket Delete API Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Ticket Dashboard Count API View (GET)
# -------------------------------------------------------------------
class TicketDashboardCountAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get ticket count grouped by status",
        responses={
            200: "Ticket count response",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def get(self, request):
        if not _has_tickets_permission(request.user, "view"):
            return _ticket_permission_denied("view")

        try:
            queryset = Ticket.objects.filter(is_deleted=False)

            response_data = {
                "new": queryset.filter(status="new").count(),
                "pending": queryset.filter(status="pending").count(),
                "resolved": queryset.filter(status="resolved").count(),
                "closed": queryset.filter(status="closed").count(),
                "total": queryset.count(),
            }

            return Response(
                response_data,
                status=status.HTTP_200_OK,
            )

        except Exception:
            logger.error("Dashboard Count API Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


