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

from restapi.models import Lead, Clinic
from restapi.serializers.lead_serializer import LeadSerializer, LeadReadSerializer
from restapi.services.zapier_service import send_to_zapier
from restapi.utils.permissions import has_action_permission_for_labels

LEAD_LABELS = ["leads hub"]

logger = logging.getLogger(__name__)


# =====================================================
# 🔥 HELPER: GET CLINIC FROM REQUEST
# =====================================================
def get_request_clinic(request):
    clinic_id = request.headers.get("X-Clinic-Id") or request.query_params.get("clinic_id")

    if not clinic_id:
        raise ValidationError({"clinic": "Clinic is required"})

    try:
        return Clinic.objects.get(id=clinic_id)
    except Clinic.DoesNotExist:
        raise ValidationError({"clinic": "Invalid clinic"})


# -------------------------------------------------------------------
# Lead Create API View (POST)
# -------------------------------------------------------------------
class LeadCreateAPIView(APIView):

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description="Create a new lead",
        request_body=LeadSerializer,
        responses={201: LeadReadSerializer, 400: "Validation Error", 500: "Internal Server Error"},
        tags=["Leads"],
    )
    def post(self, request):

        if not has_action_permission_for_labels(request.user, "add", LEAD_LABELS):
            return Response({"error": "You do not have permission to add leads."}, status=403)

        try:
            serializer = LeadSerializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)

            lead = serializer.save()

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

            return Response(LeadReadSerializer(lead).data, status=201)

        except ValidationError as ve:
            logger.warning(f"Lead validation failed: {ve.detail}")
            return Response({"error": ve.detail}, status=400)

        except Exception:
            logger.error("Unhandled Lead Create Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=500)


# -------------------------------------------------------------------
# Lead Update API View (PUT)
# -------------------------------------------------------------------
class LeadUpdateAPIView(APIView):

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description="Update an existing lead",
        request_body=LeadSerializer,
        responses={200: LeadReadSerializer, 400: "Validation Error", 404: "Lead not found"},
        tags=["Leads"],
    )
    def put(self, request, lead_id):

        if not has_action_permission_for_labels(request.user, "edit", LEAD_LABELS):
            return Response({"error": "You do not have permission to edit leads."}, status=403)

        try:
            clinic = get_request_clinic(request)

            lead = Lead.objects.get(id=lead_id)

            # ✅ CLINIC CHECK
            if lead.clinic != clinic:
                return Response({"error": "Unauthorized"}, status=403)

            serializer = LeadSerializer(lead, data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)

            updated_lead = serializer.save()

            send_to_zapier({
                "event": "lead_updated",
                "lead_id": str(updated_lead.id),
                "lead_status": updated_lead.lead_status,
                "assigned_to_id": updated_lead.assigned_to_id,
            })

            return Response(LeadReadSerializer(updated_lead).data, status=200)

        except Lead.DoesNotExist:
            raise NotFound("Lead not found")

        except ValidationError as ve:
            return Response({"error": ve.detail}, status=400)

        except Exception:
            logger.error("Unhandled Lead Update Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=500)


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
            return Response({"error": "No permission"}, status=403)

        try:
            clinic = get_request_clinic(request)

            queryset = Lead.objects.filter(
                clinic=clinic,
                is_deleted=False
            ).order_by("-created_at")

            # 🔽 KEEP YOUR FILTERS
            lead_status = request.query_params.get("lead_status")
            assigned_to = request.query_params.get("assigned_to")

            if lead_status:
                queryset = queryset.filter(lead_status=lead_status)

            if assigned_to:
                queryset = queryset.filter(assigned_to_id=assigned_to)

            serializer = LeadReadSerializer(queryset, many=True, context={"request": request})
            return Response(serializer.data, status=200)

        except ValidationError as ve:
            return Response({"error": ve.detail}, status=400)

        except Exception:
            logger.error("Lead List Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=500)


# -------------------------------------------------------------------
# Lead Get API (GET BY ID)
# -------------------------------------------------------------------
class LeadGetAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get lead by ID",
        responses={200: LeadReadSerializer},
        tags=["Leads"]
    )
    def get(self, request, lead_id):

        if not has_action_permission_for_labels(request.user, "view", LEAD_LABELS):
            return Response({"error": "No permission"}, status=403)

        try:
            clinic = get_request_clinic(request)

            lead = get_object_or_404(
                Lead.objects.select_related("clinic", "department", "campaign"),
                id=lead_id,
                clinic=clinic   # ✅ FIX
            )

            return Response(LeadReadSerializer(lead).data, status=200)

        except ValidationError as ve:
            return Response({"error": ve.detail}, status=400)

        except Exception:
            logger.error("Lead Get Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=500)


# -------------------------------------------------------------------
# Lead Activate API
# -------------------------------------------------------------------
class LeadActivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, lead_id):
        try:
            clinic = get_request_clinic(request)
            lead = Lead.objects.get(id=lead_id)

            if lead.clinic != clinic:
                return Response({"error": "Unauthorized"}, status=403)

            lead.is_active = True
            lead.save(update_fields=["is_active"])

            return Response({"message": "Lead activated successfully"}, status=200)

        except Lead.DoesNotExist:
            raise NotFound("Lead not found")


# -------------------------------------------------------------------
# Lead Inactivate API
# -------------------------------------------------------------------
class LeadInactivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, lead_id):
        try:
            clinic = get_request_clinic(request)
            lead = Lead.objects.get(id=lead_id)

            if lead.clinic != clinic:
                return Response({"error": "Unauthorized"}, status=403)

            lead.is_active = False
            lead.save(update_fields=["is_active"])

            return Response({"message": "Lead inactivated successfully"}, status=200)

        except Lead.DoesNotExist:
            raise NotFound("Lead not found")


# -------------------------------------------------------------------
# Lead Soft Delete API
# -------------------------------------------------------------------
class LeadSoftDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, lead_id):
        try:
            clinic = get_request_clinic(request)
            lead = Lead.objects.get(id=lead_id)

            if lead.clinic != clinic:
                return Response({"error": "Unauthorized"}, status=403)

            lead.is_deleted = True
            lead.is_active = False
            lead.save(update_fields=["is_deleted", "is_active"])

            return Response({"message": "Lead deleted"}, status=200)

        except Lead.DoesNotExist:
            raise NotFound("Lead not found")

    def delete(self, request, lead_id):
        return self.patch(request, lead_id) 