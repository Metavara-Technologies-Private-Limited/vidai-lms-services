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
from django.db.models import Q, Prefetch

from restapi.models import Lead, Clinic, PipelineStage, Department
from restapi.serializers.lead_serializer import LeadSerializer, LeadReadSerializer
from restapi.services.zapier_service import send_to_zapier
from restapi.utils.permissions import (
    has_action_permission_for_labels,
    normalize_role_name,
)
from restapi.models.twilio import TwilioCall, TwilioMessage
from restapi.models.lead_mail import LeadEmail
from django.db.models import OuterRef, Subquery
from django.db.models import DateTimeField
from django.db.models.functions import Greatest, Coalesce
from restapi.services.patient_sync_service import sync_patient_to_external_system

LEAD_LABELS = ["leads hub"]

logger = logging.getLogger(__name__)


# =====================================================
# 🔥 HELPER: GET CLINIC FROM REQUEST
# =====================================================
def get_request_clinic(request):
    clinic_id = request.query_params.get("clinic_id") or request.headers.get(
        "X-Clinic-Id"
    )

    if not clinic_id:
        raise ValidationError({"clinic": "Clinic is required"})

    try:
        return Clinic.objects.get(id=clinic_id)
    except Clinic.DoesNotExist:
        raise ValidationError({"clinic": "Invalid clinic"})


def get_request_user_role(request):
    role = getattr(getattr(request.user, "profile", None), "role", None)
    return normalize_role_name(getattr(role, "name", ""))


def get_request_employee(request):
    return getattr(request.user, "employee", None)


def is_restricted_lead_user(request):
    return get_request_user_role(request) == "user"


def apply_lead_visibility_scope(queryset, request):
    if not is_restricted_lead_user(request):
        return queryset

    employee = get_request_employee(request)
    user = getattr(request, "user", None)

    candidate_ids = []
    if employee and getattr(employee, "id", None):
        candidate_ids.append(employee.id)
    if user and getattr(user, "id", None):
        candidate_ids.append(user.id)

    candidate_ids = list({int(value) for value in candidate_ids if value is not None})

    if not candidate_ids:
        return queryset.none()

    return queryset.filter(
        Q(created_by_id__in=candidate_ids)
        | Q(personal_id__in=candidate_ids)
        | Q(assigned_to_id__in=candidate_ids)
    )


def get_scoped_lead_or_404(request, clinic, lead_id):
    # =====================================================
    # ✅ OPTIMIZATION: Use select_related() for all FK relations
    #    and prefetch_related() for M2M relations to eliminate N+1 queries
    # =====================================================
    queryset = Lead.objects.select_related(
        "clinic",
        "department",
        "campaign",
        "referral_department",
        "referral_source",
        "stage",
        "converted_at_stage",
    ).prefetch_related(
        "documents",
        "treatment_interest",
    ).filter(
        id=lead_id,
        clinic=clinic,
    )
    return get_object_or_404(apply_lead_visibility_scope(queryset, request))


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
            return Response(
                {"error": "You do not have permission to add leads."},
                status=403
            )

        try:
            clinic = get_request_clinic(request)

            stage_id = request.data.get("stage_id")
            pipeline_id = request.data.get("pipeline_id")

            if stage_id:

                stage = PipelineStage.objects.filter(
                    id=stage_id,
                    is_active=True,
                    is_deleted=False
                ).select_related("pipeline").first()

                if not stage:
                    raise ValidationError({"stage_id": "Invalid stage"})

                if str(stage.pipeline.clinic_id) != str(clinic.id):
                    raise ValidationError({
                        "stage_id": "Stage does not belong to this clinic"
                    })

                if pipeline_id and str(stage.pipeline_id) != str(pipeline_id):
                    raise ValidationError({
                        "stage_id": "Stage does not belong to selected pipeline"
                    })

            # =====================================================
            # DATA COPY
            # =====================================================
            data = request.data.copy()

            # =====================================================
            # 🔥 DOCUMENT FIX
            # =====================================================
            if hasattr(request, "FILES"):

                files = request.FILES.getlist("documents")

                if files:
                    data.setlist("documents", files)

            # =====================================================
            # 🔥 TREATMENT INTEREST FIX
            # =====================================================
            if "treatment_interest" in data:

                # multipart/form-data
                if hasattr(data, "getlist"):

                    treatment_interest = data.getlist("treatment_interest")

                    if not treatment_interest:
                        single_interest = data.get("treatment_interest")

                        if single_interest:
                            treatment_interest = [single_interest]

                    data.setlist("treatment_interest", treatment_interest)

                # application/json
                else:

                    treatment_interest = data.get("treatment_interest", [])

                    if treatment_interest in [None, "", "null"]:
                        treatment_interest = []

                    if not isinstance(treatment_interest, list):
                        treatment_interest = [treatment_interest]

                    data["treatment_interest"] = treatment_interest

            serializer = LeadSerializer(
                data=data,
                context={"request": request}
            )

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

            return Response(
                LeadReadSerializer(lead).data,
                status=201
            )

        except ValidationError as ve:
            return Response({"error": ve.detail}, status=400)

        except Exception:
            logger.error(
                "Unhandled Lead Create Error:\n" +
                traceback.format_exc()
            )

            return Response(
                {"error": "Internal Server Error"},
                status=500
            )

# -------------------------------------------------------------------
# Lead Update API View (PUT)
# -------------------------------------------------------------------
class LeadUpdateAPIView(APIView):

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description="Update an existing lead",
        request_body=LeadSerializer,
        responses={200: LeadReadSerializer},
        tags=["Leads"],
    )
    def put(self, request, lead_id):

        if not has_action_permission_for_labels(
            request.user,
            "edit",
            LEAD_LABELS
        ):
            return Response(
                {"error": "You do not have permission to edit leads."},
                status=403
            )

        try:

            logger.info(
                "Lead Update API Started | lead_id=%s",
                lead_id
            )

            clinic = get_request_clinic(request)

            lead = get_scoped_lead_or_404(
                request,
                clinic,
                lead_id
            )

            data = request.data.copy()

            # =====================================================
            # 🔥 DOCUMENT FIX
            # =====================================================
            if hasattr(request, "FILES"):

                files = request.FILES.getlist("documents")

                if files:
                    data.setlist("documents", files)

            # =====================================================
            # 🔥 TREATMENT INTEREST FIX
            # =====================================================
            if "treatment_interest" in data:

                # multipart/form-data
                if hasattr(data, "getlist"):

                    treatment_interest = data.getlist("treatment_interest")

                    if not treatment_interest:

                        single_interest = data.get("treatment_interest")

                        if single_interest:
                            treatment_interest = [single_interest]

                    data.setlist("treatment_interest", treatment_interest)

                # application/json
                else:

                    treatment_interest = data.get("treatment_interest", [])

                    if treatment_interest in [None, "", "null"]:
                        treatment_interest = []

                    if not isinstance(treatment_interest, list):
                        treatment_interest = [treatment_interest]

                    data["treatment_interest"] = treatment_interest

            # =====================================================
            # STATUS FIX
            # =====================================================
            if "lead_status" in data:

                status_val = str(
                    data.get("lead_status")
                ).strip().lower()

                data["lead_status"] = status_val

                request._full_data = request.data.copy()
                request._full_data["lead_status"] = status_val

                logger.info(
                    "Lead Update Requested Status: %s",
                    status_val
                )

            # =====================================================
            # STAGE VALIDATION
            # =====================================================
            stage_id = data.get("stage_id")
            pipeline_id = data.get("pipeline_id")

            if stage_id:

                stage = PipelineStage.objects.filter(
                    id=stage_id,
                    is_active=True,
                    is_deleted=False
                ).select_related("pipeline").first()

                if not stage:
                    raise ValidationError({"stage_id": "Invalid stage"})

                if str(stage.pipeline.clinic_id) != str(clinic.id):
                    raise ValidationError({
                        "stage_id": "Stage does not belong to this clinic"
                    })

                if pipeline_id and str(stage.pipeline_id) != str(pipeline_id):
                    raise ValidationError({
                        "stage_id": "Stage does not belong to selected pipeline"
                    })

            old_status = (lead.lead_status or "").lower()

            logger.info(
                "STEP 1 - Starting serializer validation | lead=%s",
                lead.id
            )

            serializer = LeadSerializer(
                lead,
                data=data,
                context={"request": request},
                partial=True
            )

            serializer.is_valid(raise_exception=True)

            logger.info(
                "STEP 2 - Serializer validation completed | lead=%s",
                lead.id
            )

            updated_lead = serializer.save()

            logger.info(
                "STEP 3 - Serializer save completed | lead=%s",
                updated_lead.id
            )

            new_status = (updated_lead.lead_status or "").lower()

            # =====================================================
            # EXTERNAL PATIENT SYNC
            # =====================================================
            if (
                old_status != "converted"
                and new_status == "converted"
                and not updated_lead.external_patient_id
            ):

                try:

                    logger.info(
                        "STEP 4 - Starting external patient sync | lead=%s",
                        updated_lead.id
                    )

                    sync_patient_to_external_system(updated_lead)

                    logger.info(
                        "STEP 5 - External patient sync completed | lead=%s",
                        updated_lead.id
                    )

                except Exception:

                    updated_lead.external_patient_sync_error = traceback.format_exc()

                    updated_lead.save(
                        update_fields=["external_patient_sync_error"]
                    )

                    logger.exception(
                        "External patient sync failed for lead %s",
                        updated_lead.id
                    )

            logger.info(
                "Lead %s updated | status=%s | converted_at_stage=%s | converted_at_status=%s",
                updated_lead.id,
                updated_lead.lead_status,
                updated_lead.converted_at_stage_id,
                updated_lead.converted_at_status
            )

            # =====================================================
            # ZAPIER SYNC
            # =====================================================
            try:

                logger.info(
                    "STEP 6 - Starting Zapier sync | lead=%s",
                    updated_lead.id
                )

                send_to_zapier({
                    "event": "lead_updated",
                    "lead_id": str(updated_lead.id),
                    "lead_status": updated_lead.lead_status,
                    "assigned_to_id": updated_lead.assigned_to_id,
                })

                logger.info(
                    "STEP 7 - Zapier sync completed | lead=%s",
                    updated_lead.id
                )

            except Exception:

                logger.exception(
                    "Zapier sync failed for lead %s",
                    updated_lead.id
                )

            logger.info(
                "Lead Update API Completed Successfully | lead=%s",
                updated_lead.id
            )

            return Response(
                LeadReadSerializer(updated_lead).data,
                status=200
            )

        except ValidationError as ve:

            logger.error(
                "Lead Update Validation Error:\n%s",
                traceback.format_exc()
            )

            return Response(
                {"error": ve.detail},
                status=400
            )

        except Exception:

            logger.error(
                "Unhandled Lead Update Error:\n%s",
                traceback.format_exc()
            )

            return Response(
                {"error": "Internal Server Error"},
                status=500
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
            return Response({"error": "No permission"}, status=403)

        try:
            clinic = get_request_clinic(request)
            latest_call_subquery = (
                TwilioCall.objects.filter(
                    lead=OuterRef("pk"),
                    status__in=["completed", "answered", "in-progress"]
                )
                .order_by("-created_at")
                .values("created_at")[:1]
            )

            latest_sms_subquery = (
                TwilioMessage.objects.filter(
                    lead=OuterRef("pk"),
                    status__in=[
                        "queued",
                        "queued_via_zapier",
                        "sent",
                        "delivered",
                    ]
                )
                .order_by("-created_at")
                .values("created_at")[:1]
            )

            latest_email_subquery = (
                LeadEmail.objects.filter(
                    lead=OuterRef("pk"),
                    status="SENT",
                    sent_at__isnull=False
                )
                .order_by("-sent_at")
                .values("sent_at")[:1]
            )


            # =====================================================
            # ✅ OPTIMIZATION: Use select_related() for all FK relations
            #    and prefetch_related() for M2M relations to eliminate N+1 queries
            # =====================================================
            queryset = apply_lead_visibility_scope(
                Lead.objects.filter(clinic=clinic, is_deleted=False)
                .select_related(
                    "clinic",
                    "department",
                    "campaign",
                    "referral_department",
                    "referral_source",
                    "stage",
                    "converted_at_stage",
                )
                .prefetch_related(
                    "documents",
                    "treatment_interest",
                )
                .annotate(
                    latest_call_at=Subquery(
                        latest_call_subquery,
                        output_field=DateTimeField(),
                    ),
                    latest_sms_at=Subquery(
                        latest_sms_subquery,
                        output_field=DateTimeField(),
                    ),
                    latest_email_at=Subquery(
                        latest_email_subquery,
                        output_field=DateTimeField(),
                    ),
                )
                .annotate(
                    last_interaction_at_db=Greatest(
                        Coalesce("latest_call_at", "created_at"),
                        Coalesce("latest_sms_at", "created_at"),
                        Coalesce("latest_email_at", "created_at"),
                    )
                )
                .order_by("-created_at"),
                request,
            )

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

            lead = get_scoped_lead_or_404(request, clinic, lead_id)

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
            lead = get_scoped_lead_or_404(request, clinic, lead_id)

            lead.is_active = True
            lead.save(update_fields=["is_active"])

            return Response({"message": "Lead activated successfully"}, status=200)

        except Exception:
            raise NotFound("Lead not found")


# -------------------------------------------------------------------
# Lead Inactivate API
# -------------------------------------------------------------------
class LeadInactivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, lead_id):
        try:
            clinic = get_request_clinic(request)
            lead = get_scoped_lead_or_404(request, clinic, lead_id)

            lead.is_active = False
            lead.save(update_fields=["is_active"])

            return Response({"message": "Lead inactivated successfully"}, status=200)

        except Exception:
            raise NotFound("Lead not found")


# -------------------------------------------------------------------
# Lead Soft Delete API
# -------------------------------------------------------------------
class LeadSoftDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, lead_id):
        try:
            clinic = get_request_clinic(request)
            lead = get_scoped_lead_or_404(request, clinic, lead_id)

            lead.is_deleted = True
            lead.is_active = False
            lead.save(update_fields=["is_deleted", "is_active"])

            return Response({"message": "Lead deleted"}, status=200)

        except Exception:
            raise NotFound("Lead not found")

    def delete(self, request, lead_id):
        return self.patch(request, lead_id)
