# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import logging
import traceback

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema

from django.shortcuts import get_object_or_404

from restapi.models import Lead
from restapi.serializers.lead_serializer import LeadSerializer, LeadReadSerializer
from restapi.services.zapier_service import send_to_zapier
from restapi.utils.permissions import has_action_permission_for_labels

# Aliases used across the app for the Leads Hub permission category
LEAD_LABELS = ["leads hub"]

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Lead Create API View (POST)
# -------------------------------------------------------------------
class LeadCreateAPIView(APIView):
    """
    Create Lead API (Supports JSON + File Upload)
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description="Create a new lead",
        request_body=LeadSerializer,
        responses={
            201: LeadReadSerializer,
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Leads"],
    )
    def post(self, request):
        print("STEP 1: LeadCreateAPIView HIT")

        if not has_action_permission_for_labels(request.user, "add", LEAD_LABELS):
            return Response(
                {"error": "You do not have permission to add leads."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            print("STEP 2: Incoming request data:")
            print(request.data)

            serializer = LeadSerializer(
                data=request.data,
                context={"request": request},
            )

            print("STEP 3: Serializer initialized")

            serializer.is_valid(raise_exception=True)
            print("STEP 4: Serializer validated successfully")

            lead = serializer.save()
            print(f"STEP 5: Lead saved successfully | ID = {lead.id}")

            print("STEP 6: Sending data to Zapier")

            send_to_zapier({
                "event": "lead_created",
                "lead_id": str(lead.id),
                "clinic_id": lead.clinic.id,
                "campaign_id": str(lead.campaign.id) if lead.campaign else None,
                "full_name": lead.full_name,
                "contact_no": lead.contact_no,
                "email": lead.email,
                "lead_status": lead.lead_status,
                "assigned_to_id": lead.assigned_to_id,
                
            })

            print("STEP 7: Zapier call completed")

            response_data = LeadReadSerializer(lead).data
            print("STEP 8: Response prepared")

            return Response(
                response_data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as ve:
            print("VALIDATION ERROR OCCURRED")
            print(ve.detail)

            logger.warning(f"Lead validation failed: {ve.detail}")

            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            print("UNHANDLED EXCEPTION OCCURRED")
            print(traceback.format_exc())

            logger.error(
                "Unhandled Lead Create Error:\n" + traceback.format_exc()
            )

            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Lead Update API View (PUT)
# -------------------------------------------------------------------
class LeadUpdateAPIView(APIView):
    """
    Update an existing Lead
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description="Update an existing lead",
        request_body=LeadSerializer,
        responses={
            200: LeadReadSerializer,
            400: "Validation Error",
            404: "Lead not found",
            500: "Internal Server Error",
        },
        tags=["Leads"],
    )
    def put(self, request, lead_id):
        if not has_action_permission_for_labels(request.user, "edit", LEAD_LABELS):
            return Response(
                {"error": "You do not have permission to edit leads."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            lead = Lead.objects.get(id=lead_id)

            serializer = LeadSerializer(
                lead,
                data=request.data,
                context={"request": request}
            )

            serializer.is_valid(raise_exception=True)

            updated_lead = serializer.save()

            send_to_zapier({
                "event": "lead_updated",
                "lead_id": str(updated_lead.id),
                "lead_status": updated_lead.lead_status,
                "assigned_to_id": updated_lead.assigned_to_id,
                
            })

            return Response(
                LeadReadSerializer(updated_lead).data,
                status=status.HTTP_200_OK
            )

        except Lead.DoesNotExist:
            logger.warning("Lead not found")
            raise NotFound("Lead not found")

        except ValidationError as ve:
            logger.warning(
                f"Lead update validation failed: {ve.detail}"
            )
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception:
            logger.error(
                "Unhandled Lead Update Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# -------------------------------------------------------------------
# Lead List API View (GET)
# -------------------------------------------------------------------
class LeadListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get all active leads",
        responses={200: LeadReadSerializer(many=True)},
        tags=["Leads"]
    )
    def get(self, request):
        if not has_action_permission_for_labels(request.user, "view", LEAD_LABELS):
            return Response(
                {"error": "You do not have permission to view leads."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            queryset = Lead.objects.filter(
                is_deleted=False
            ).order_by("-created_at")

            clinic_id = request.query_params.get("clinic")
            lead_status = request.query_params.get("lead_status")
            assigned_to = request.query_params.get("assigned_to")

            if clinic_id:
                queryset = queryset.filter(clinic_id=clinic_id)

            if lead_status:
                queryset = queryset.filter(lead_status=lead_status)

            if assigned_to:
                queryset = queryset.filter(assigned_to_id=assigned_to)

            serializer = LeadReadSerializer(
                queryset,
                many=True,
                context={"request": request},
            )

            return Response(
                serializer.data,
                status=status.HTTP_200_OK
            )

        except ValidationError as validation_error:
            logger.warning(f"Lead list validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Lead List Error:\n" + traceback.format_exc())

            # Fallback for corrupted production rows/files: return safe minimal
            # payload so the list endpoint does not hard-fail with 500.
            try:
                fallback_rows = []
                for lead in queryset:
                    created_at = getattr(lead, "created_at", None)
                    fallback_rows.append(
                        {
                            "id": str(getattr(lead, "id", "")),
                            "full_name": getattr(lead, "full_name", "") or "",
                            "contact_no": getattr(lead, "contact_no", "") or "",
                            "lead_status": getattr(lead, "lead_status", "") or "",
                            "created_at": created_at.isoformat() if created_at else None,
                        }
                    )

                return Response(fallback_rows, status=status.HTTP_200_OK)
            except Exception:
                logger.error("Lead List Fallback Error:\n" + traceback.format_exc())
                return Response(
                    {"error": "Internal Server Error"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

# -------------------------------------------------------------------
# Lead List API using ID (GET)
# -------------------------------------------------------------------
class LeadGetAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get lead by ID",
        responses={200: LeadReadSerializer, 404: "Lead not found"},
        tags=["Leads"]
    )
    def get(self, request, lead_id):
        if not has_action_permission_for_labels(request.user, "view", LEAD_LABELS):
            return Response(
                {"error": "You do not have permission to view leads."},
                status=status.HTTP_403_FORBIDDEN,
            )

        lead = get_object_or_404(
            Lead.objects.select_related(
                "clinic",
                "department",
                "campaign",
            ),
            id=lead_id
        )

        try:
            payload = LeadReadSerializer(
                lead,
                context={"request": request},
            ).data
            return Response(payload, status=status.HTTP_200_OK)
        except Exception:
            logger.error("Lead Get Error:\n" + traceback.format_exc())

            created_at = getattr(lead, "created_at", None)
            fallback = {
                "id": str(getattr(lead, "id", "")),
                "full_name": getattr(lead, "full_name", "") or "",
                "contact_no": getattr(lead, "contact_no", "") or "",
                "lead_status": getattr(lead, "lead_status", "") or "",
                "created_at": created_at.isoformat() if created_at else None,
            }
            return Response(fallback, status=status.HTTP_200_OK)

# -------------------------------------------------------------------
# Lead Activate API (Post)
# -------------------------------------------------------------------
class LeadActivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Activate a lead",
        tags=["Leads"]
    )
    def post(self, request, lead_id):
        if not has_action_permission_for_labels(request.user, "edit", LEAD_LABELS):
            return Response(
                {"error": "You do not have permission to modify leads."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            lead = Lead.objects.get(id=lead_id)

            lead.is_active = True
            lead.save(update_fields=["is_active"])

            return Response(
                {"message": "Lead activated successfully"},
                status=status.HTTP_200_OK
            )

        except Lead.DoesNotExist:
            raise NotFound("Lead not found")

# -------------------------------------------------------------------
# Lead In_Activate API (Patch)
# -------------------------------------------------------------------
class LeadInactivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Inactivate a lead",
        tags=["Leads"]
    )
    def patch(self, request, lead_id):
        if not has_action_permission_for_labels(request.user, "edit", LEAD_LABELS):
            return Response(
                {"error": "You do not have permission to modify leads."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            lead = Lead.objects.get(id=lead_id)

            lead.is_active = False
            lead.save(update_fields=["is_active"])

            return Response(
                {"message": "Lead inactivated successfully"},
                status=status.HTTP_200_OK
            )

        except Lead.DoesNotExist:
            raise NotFound("Lead not found")

# -------------------------------------------------------------------
# Lead Soft Delete (Patch)
# -------------------------------------------------------------------
class LeadSoftDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Soft delete a lead",
        tags=["Leads"]
    )
    def patch(self, request, lead_id):
        if not has_action_permission_for_labels(request.user, "edit", LEAD_LABELS):
            return Response(
                {"error": "You do not have permission to delete leads."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            lead = Lead.objects.get(id=lead_id)

            lead.is_deleted = True
            lead.is_active = False
            lead.save(update_fields=["is_deleted", "is_active"])

            return Response(
                {"message": "Lead soft deleted successfully"},
                status=status.HTTP_200_OK
            )

        except Lead.DoesNotExist:
            raise NotFound("Lead not found")

    def delete(self, request, lead_id):
        return self.patch(request, lead_id)