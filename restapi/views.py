# Python Standard Library

import logging
import traceback

# Django Imports

from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db import transaction

# Third-Party Imports (DRF + Swagger)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from django.shortcuts import redirect
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
import requests
import secrets
from django.http import HttpResponseRedirect
from datetime import datetime

# Project Imports – Models

from restapi.models import (
    Clinic,
    Ticket,
    Employee,
    Document,
    LeadNote,
    TicketTimeline,
    CampaignSocialMediaConfig,
    Pipeline,
    PipelineStage,
    TemplateMail,
    TemplateSMS,
    TemplateWhatsApp,
    CampaignEmailConfig,
)

from .models import Lead, Campaign, Lab

# Project Imports – Serializers

from restapi.serializers.ticket_serializer import (
    TicketListSerializer,
    TicketDetailSerializer,
    TicketWriteSerializer,
    LabReadSerializer,
    LabWriteSerializer,
    
)

from restapi.serializers.clinic import (
    ClinicSerializer,
    ClinicReadSerializer,
)

from restapi.serializers.employee import (
    EmployeeCreateSerializer,
    EmployeeReadSerializer,
    UserCreateSerializer,
)

from restapi.serializers.lead_note_serializers import (
    LeadNoteSerializer,
    LeadNoteReadSerializer,
)
from restapi.serializers.lead_serializer import (
    LeadSerializer,
    LeadReadSerializer,
)

from restapi.serializers.campaign_serializer import (
    CampaignSerializer,
    CampaignReadSerializer,
    SocialMediaCampaignSerializer,
    EmailCampaignCreateSerializer
)

from restapi.serializers.mailchimp_serializer import (
    MailchimpWebhookSerializer,
)
from restapi.services.mailchimp_service import (
    create_mailchimp_event,
)

from restapi.serializers.campaign_social_post_serializer import (
    CampaignSocialPostCallbackSerializer
)
from restapi.services.campaign_social_post_service import (
    handle_zapier_callback
)

from restapi.serializers.twilio_serializers import (
    SendSMSSerializer,
    MakeCallSerializer,
)
from restapi.services.twilio_service import send_sms, make_call


from restapi.serializers.pipeline_serializer import (
    PipelineSerializer,
    PipelineReadSerializer,
)

from restapi.serializers.template_serializers import (
    TemplateMailSerializer,
    TemplateSMSSerializer,
    TemplateWhatsAppSerializer,

    TemplateMailReadSerializer,
    TemplateSMSReadSerializer,
    TemplateWhatsAppReadSerializer,
)
# Project Imports – Services

from restapi.services.zapier_service import send_to_zapier
from restapi.services.pipeline_service import (
    add_stage,
    update_stage,
    save_stage_rules,
    save_stage_fields,
    
)

from restapi.services.lead_note_service import (
    create_lead_note,
    update_lead_note,
    delete_lead_note,
)


logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Create Clinic (POST)
# -------------------------------------------------------------------
class ClinicCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create a new clinic with departments",
        request_body=ClinicSerializer,
        responses={
            201: ClinicReadSerializer,
            400: "Validation Error",
            500: "Internal Server Error",
        },
    )
    def post(self, request):
        try:
            serializer = ClinicSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            clinic = serializer.save()

            return Response(
                ClinicReadSerializer(clinic).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as ve:
            logger.warning(f"Clinic validation failed: {ve.detail}")
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Clinic Create Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Update Clinic (PUT)
# -------------------------------------------------------------------
class ClinicUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Update an existing clinic and its departments",
        request_body=ClinicSerializer,
        responses={
            200: ClinicReadSerializer,
            400: "Validation Error",
            404: "Clinic not found",
            500: "Internal Server Error",
        },
    )
    def put(self, request, clinic_id):
        try:
            clinic = Clinic.objects.get(id=clinic_id)

            serializer = ClinicSerializer(
                clinic,
                data=request.data  # PUT = full update
            )
            serializer.is_valid(raise_exception=True)

            updated_clinic = serializer.save()

            return Response(
                ClinicReadSerializer(updated_clinic).data,
                status=status.HTTP_200_OK,
            )

        except Clinic.DoesNotExist:
            logger.warning("Clinic not found")
            raise NotFound("Clinic not found")

        except ValidationError as ve:
            logger.warning(
                f"Clinic update validation failed: {ve.detail}"
            )
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Clinic Update Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
# -------------------------------------------------------------------
# Get Clinic by ID (GET)
# -------------------------------------------------------------------
class GetClinicView(APIView):

    @swagger_auto_schema(
        operation_description="Retrieve clinic details with departments",
        responses={
            200: ClinicReadSerializer,
            404: "Clinic not found",
            500: "Internal Server Error",
        },
    )
    def get(self, request, clinic_id):
        try:
            clinic = Clinic.objects.get(id=clinic_id)

            serializer = ClinicReadSerializer(clinic)

            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )

        except Clinic.DoesNotExist:
            raise NotFound("Clinic not found")

        except Exception:
            logger.error(
                "Unhandled Clinic Fetch Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# User Create API View (POST)
# -------------------------------------------------------------------


class UserCreateAPIView(APIView):
    
    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                "id": user.id,
                "username": user.username
            },
            status=status.HTTP_201_CREATED
        )

# -------------------------------------------------------------------
# Clinic Employees API View (GET)
# -------------------------------------------------------------------

class ClinicEmployeesAPIView(APIView):
    
    @swagger_auto_schema(
        operation_summary="Get Clinic Employees",
        operation_description="Retrieve all employees under a specific clinic",
        responses={
            200: EmployeeReadSerializer(many=True),
            401: "Unauthorized",
            404: "Clinic not found",
        },
        tags=["Clinic"]
    )
    def get(self, request, clinic_id):
        #  Validate clinic existence
        get_object_or_404(Clinic, id=clinic_id)

        #  Fetch employees for the clinic
        employees = Employee.objects.filter(clinic_id=clinic_id)

        serializer = EmployeeReadSerializer(employees, many=True)
        return Response(serializer.data)

# -------------------------------------------------------------------
# Employee Create API View (POST)
# -------------------------------------------------------------------

class EmployeeCreateAPIView(APIView):
   

    @swagger_auto_schema(
        operation_summary="Create Employee",
        operation_description="Create an employee under a clinic and department",
        request_body=EmployeeCreateSerializer,
        responses={
            201: EmployeeReadSerializer,
            400: "Validation Error",
            401: "Unauthorized"
        },
        tags=["Employee"]
    )
    def post(self, request):
        serializer = EmployeeCreateSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        employee = serializer.save()

        return Response(
            EmployeeReadSerializer(employee).data,
            status=status.HTTP_201_CREATED
        )

# =====================================================
# CREATE LEAD NOTE API
# =====================================================

class LeadNoteCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create a new note for a Lead",
        request_body=LeadNoteSerializer,
        responses={
            201: LeadNoteReadSerializer,
            400: "Validation Error",
            500: "Internal Server Error",
        },
    )
    def post(self, request):
        try:
            serializer = LeadNoteSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            note = serializer.save()

            return Response(
                LeadNoteReadSerializer(note).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as validation_error:
            logger.warning(f"Lead Note Create validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Lead Note Create Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================
# UPDATE LEAD NOTE API
# =====================================================

class LeadNoteUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Update an existing Lead note",
        request_body=LeadNoteSerializer,
        responses={
            200: LeadNoteReadSerializer,
            400: "Validation Error",
            404: "Not Found",
            500: "Internal Server Error",
        },
    )
    def put(self, request, note_id):
        try:
            note_instance = LeadNote.objects.filter(
                id=note_id,
                is_deleted=False
            ).first()

            if not note_instance:
                return Response(
                    {"error": "Lead note not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = LeadNoteSerializer(
                note_instance,
                data=request.data,
                partial=True
            )

            serializer.is_valid(raise_exception=True)
            updated_note = serializer.save()

            return Response(
                LeadNoteReadSerializer(updated_note).data,
                status=status.HTTP_200_OK,
            )

        except ValidationError as validation_error:
            logger.warning(
                f"Lead Note Update validation failed: {validation_error.detail}"
            )
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Lead Note Update Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================
# DELETE LEAD NOTE API (SOFT DELETE)
# =====================================================

class LeadNoteDeleteAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Soft delete a Lead note",
        responses={
            200: "Deleted Successfully",
            404: "Not Found",
            500: "Internal Server Error",
        },
    )
    def delete(self, request, note_id):
        try:
            note_instance = LeadNote.objects.filter(
                id=note_id,
                is_deleted=False
            ).first()

            if not note_instance:
                return Response(
                    {"error": "Lead note not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            delete_lead_note(note_instance)

            return Response(
                {"message": "Lead note deleted successfully."},
                status=status.HTTP_200_OK,
            )

        except ValidationError as validation_error:
            logger.warning(f"Lead Note Delete validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Lead Note Delete Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================
# LIST NOTES BY LEAD API
# =====================================================

class LeadNoteListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="List all notes for a specific Lead",
        responses={
            200: LeadNoteReadSerializer(many=True),
            500: "Internal Server Error",
        },
    )
    def get(self, request, lead_id):
        try:
            notes = LeadNote.objects.filter(
                lead_id=lead_id,
                is_deleted=False
            ).order_by("-created_at")

            serializer = LeadNoteReadSerializer(notes, many=True)

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Lead Note List Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Lead Create API View (POST)
# -------------------------------------------------------------------

class LeadCreateAPIView(APIView):
    """
    Create Lead API (Supports JSON + File Upload)
    """

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
        print(" STEP 1: LeadCreateAPIView HIT")

        try:
            print(" STEP 2: Incoming request data:")
            print(request.data)

            serializer = LeadSerializer(
                data=request.data,
                context={"request": request},
            )

            print("STEP 3: Serializer initialized")

            serializer.is_valid(raise_exception=True)
            print("STEP 4: Serializer validated successfully")

            lead = serializer.save()
            print(f"💾 STEP 5: Lead saved successfully | ID = {lead.id}")

            # ===============================
            # ZAPIER INTEGRATION
            # ===============================
            print("🔔 STEP 6: Sending data to Zapier")

            send_to_zapier({
                "event": "lead_created",
                "lead_id": str(lead.id),
                "clinic_id": lead.clinic.id,
                "campaign_id": str(lead.campaign.id) if lead.campaign else None,
                "full_name": lead.full_name,
                "contact_no": lead.contact_no,
                "email": lead.email,
                "lead_status": lead.lead_status,
                "assigned_to_id": (
                    lead.assigned_to.id if lead.assigned_to else None
                ),
            })

            print("🚀 STEP 7: Zapier call completed")

            response_data = LeadReadSerializer(lead).data
            print("📤 STEP 8: Response prepared")

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
        try:
            #  fetch existing lead
            lead = Lead.objects.get(id=lead_id)

            #  PUT = full update (instance + data)
            serializer = LeadSerializer(
                lead,
                data=request.data,
                context={"request": request}
            )

            serializer.is_valid(raise_exception=True)

            #  calls update_lead()
            updated_lead = serializer.save()

            #  ZAPIER
            send_to_zapier({
                "event": "lead_updated",
                "lead_id": str(updated_lead.id),
                "lead_status": updated_lead.lead_status,
                "assigned_to_id": (
                    updated_lead.assigned_to.id
                    if updated_lead.assigned_to else None
                ),
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

    @swagger_auto_schema(
        operation_description="Get all active leads",
        responses={200: LeadReadSerializer(many=True)},
        tags=["Leads"]
    )
    def get(self, request):
        try:
            # -------------------------------------------------
            # Base Query (Exclude Deleted)
            # -------------------------------------------------
            queryset = Lead.objects.filter(
                is_deleted=False
            ).order_by("-created_at")

            # -------------------------------------------------
            # Optional Filters
            # -------------------------------------------------

            clinic_id = request.query_params.get("clinic")
            lead_status = request.query_params.get("lead_status")
            assigned_to = request.query_params.get("assigned_to")

            if clinic_id:
                queryset = queryset.filter(clinic_id=clinic_id)

            if lead_status:
                queryset = queryset.filter(lead_status=lead_status)

            if assigned_to:
                queryset = queryset.filter(assigned_to_id=assigned_to)

            serializer = LeadReadSerializer(queryset, many=True)

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
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Lead List API using ID (GET)
# -------------------------------------------------------------------

class LeadGetAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Get lead by ID",
        responses={200: LeadReadSerializer, 404: "Lead not found"},
        tags=["Leads"]
    )
    def get(self, request, lead_id):
        lead = get_object_or_404(
            Lead.objects.select_related(
                "clinic",
                "department",
                "campaign",
                "assigned_to",
                "personal"
            ),
            id=lead_id
        )

        return Response(
            LeadReadSerializer(lead).data,
            status=status.HTTP_200_OK
        )

# -------------------------------------------------------------------
# Lead Activate API (Post)
# -------------------------------------------------------------------

class LeadActivateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Activate a lead",
        tags=["Leads"]
    )
    def post(self, request, lead_id):
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

    @swagger_auto_schema(
        operation_description="Inactivate a lead",
        tags=["Leads"]
    )
    def patch(self, request, lead_id):
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

    @swagger_auto_schema(
        operation_description="Soft delete a lead",
        tags=["Leads"]
    )
    def patch(self, request, lead_id):
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

    # Optional DELETE support
    def delete(self, request, lead_id):
        return self.patch(request, lead_id)

# -------------------------------------------------------------------
# Campaign Create API View (POST)
# -------------------------------------------------------------------

class CampaignCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description=(
            "Create a new campaign along with optional "
            "social media and email configurations"
        ),
        request_body=CampaignSerializer,        # WRITE
        responses={
            201: CampaignReadSerializer,         # READ
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Campaigns"],
    )
    def post(self, request):
        try:
            serializer = CampaignSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            campaign = serializer.save()

            channels = []

            if campaign.social_configs.filter(is_active=True).exists():
                channels.append("facebook")

            if campaign.email_configs.filter(is_active=True).exists():
                channels.append("email")

            print("ZAPIER CHANNELS →", channels)  # debug (optional)

            # 🔔 ZAPIER
            send_to_zapier({
    "event": "campaign_created",
    "campaign_id": str(campaign.id),
    "campaign_name": campaign.campaign_name,
    "clinic_id": campaign.clinic.id,
    "campaign_mode": campaign.campaign_mode,
    "status": campaign.status,
    "is_active": campaign.is_active,

    "channels": channels,

    "start_date": campaign.start_date.isoformat() if campaign.start_date else None,
    "end_date": campaign.end_date.isoformat() if campaign.end_date else None,

    "selected_start": campaign.selected_start.isoformat() if campaign.selected_start else None,
    "selected_end": campaign.selected_end.isoformat() if campaign.selected_end else None,

    "enter_time": campaign.enter_time.strftime("%H:%M") if campaign.enter_time else None,
})

            return Response(
                CampaignReadSerializer(campaign).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as ve:
            logger.warning(f"Campaign validation failed: {ve.detail}")
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Campaign Create Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
# -------------------------------------------------------------------
# Campaign Update API View (PUT)
# -------------------------------------------------------------------

class CampaignUpdateAPIView(APIView):
    """
    Update an existing Campaign
    """

    @swagger_auto_schema(
        operation_description="Update an existing campaign",
        request_body=CampaignSerializer,
        responses={
            200: CampaignReadSerializer,
            400: "Validation Error",
            404: "Campaign not found",
            500: "Internal Server Error",
        },
        tags=["Campaigns"],
    )
    def put(self, request, campaign_id):
        try:
            # ✅ fetch campaign
            campaign = Campaign.objects.get(id=campaign_id)

            serializer = CampaignSerializer(
                campaign,
                data=request.data
            )
            serializer.is_valid(raise_exception=True)

            updated_campaign = serializer.save()

            # 🔔 ZAPIER (event name should be updated, not created)
            send_to_zapier({
    "event": "campaign_created",
    "campaign_id": str(campaign.id),
    "campaign_name": campaign.campaign_name,
    "clinic_id": campaign.clinic.id,
    "campaign_mode": campaign.campaign_mode,
    "status": campaign.status,
    "is_active": campaign.is_active,

    "channels": channels,

    "start_date": campaign.start_date.isoformat() if campaign.start_date else None,
    "end_date": campaign.end_date.isoformat() if campaign.end_date else None,

    "selected_start": campaign.selected_start.isoformat() if campaign.selected_start else None,
    "selected_end": campaign.selected_end.isoformat() if campaign.selected_end else None,

    "enter_time": campaign.enter_time.strftime("%H:%M") if campaign.enter_time else None,
})

            # ✅ THIS LINE WAS MISSING
            return Response(
                CampaignReadSerializer(updated_campaign).data,
                status=status.HTTP_200_OK
            )

        except Campaign.DoesNotExist:
            logger.warning("Campaign not found")
            raise NotFound("Campaign not found")

        except ValidationError as ve:
            logger.warning(
                f"Campaign update validation failed: {ve.detail}"
            )
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception:
            logger.error(
                "Unhandled Campaign Update Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# -------------------------------------------------------------------
# Campaign List API View (GET)
# -------------------------------------------------------------------

class CampaignListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Get all campaigns with lead count",
        responses={200: CampaignReadSerializer(many=True)},
        tags=["Campaigns"]
    )
    def get(self, request):
        campaigns = Campaign.objects.all().order_by("-created_at")

        data = []
        for campaign in campaigns:
            campaign_data = CampaignReadSerializer(campaign).data
            campaign_data["lead_generated"] = campaign.leads.count()
            data.append(campaign_data)

        return Response(data, status=status.HTTP_200_OK)

# -------------------------------------------------------------------
# Campaign Get API View With ID (GET)
# -------------------------------------------------------------------

class CampaignGetAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Get campaign by ID",
        responses={200: CampaignReadSerializer},
        tags=["Campaigns"]
    )
    def get(self, request, campaign_id):
        campaign = get_object_or_404(Campaign, id=campaign_id)

        data = CampaignReadSerializer(campaign).data
        data["lead_generated"] = campaign.leads.count()

        return Response(data, status=status.HTTP_200_OK)
# -------------------------------------------------------------------
# Campaign Activate API (Post)
# -------------------------------------------------------------------

class CampaignActivateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Activate a campaign",
        tags=["Campaigns"]
    )
    def post(self, request, campaign_id):
        try:
            campaign = Campaign.objects.get(id=campaign_id)

            campaign.is_active = True
            campaign.save(update_fields=["is_active"])

            return Response(
                {"message": "Campaign activated successfully"},
                status=status.HTTP_200_OK
            )

        except Campaign.DoesNotExist:
            raise NotFound("Campaign not found")

# -------------------------------------------------------------------
# Campaign In_Activate API (Patch)
# -------------------------------------------------------------------

class CampaignInactivateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Inactivate a campaign",
        tags=["Campaigns"]
    )
    def patch(self, request, campaign_id):
        try:
            campaign = Campaign.objects.get(id=campaign_id)

            campaign.is_active = False
            campaign.save(update_fields=["is_active"])

            return Response(
                {"message": "Campaign inactivated successfully"},
                status=status.HTTP_200_OK
            )

        except Campaign.DoesNotExist:
            raise NotFound("Campaign not found")

# -------------------------------------------------------------------
# Campaign Soft Delete API (Patch)
# -------------------------------------------------------------------

class CampaignSoftDeleteAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Soft delete a campaign",
        tags=["Campaigns"]
    )
    def patch(self, request, campaign_id):
        try:
            campaign = Campaign.objects.get(id=campaign_id)

            campaign.is_deleted = True
            campaign.is_active = False
            campaign.save(update_fields=["is_deleted", "is_active"])

            return Response(
                {"message": "Campaign soft deleted successfully"},
                status=status.HTTP_200_OK
            )

        except Campaign.DoesNotExist:
            raise NotFound("Campaign not found")

    def delete(self, request, campaign_id):
        return self.patch(request, campaign_id)

class CampaignZapierCallbackAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Zapier callback to update social post status",
        request_body=CampaignSocialPostCallbackSerializer,
        responses={
            200: "Campaign social post updated successfully",
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Campaigns"],
    )
    def post(self, request):
        try:
            serializer = CampaignSocialPostCallbackSerializer(
                data=request.data
            )

            if not serializer.is_valid():
                return Response(
                    serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )

            social_post = handle_zapier_callback(
                serializer.validated_data
            )

            return Response(
                {
                    "message": "Campaign social post updated successfully",
                    "social_post_id": str(social_post.id),
                    "status": social_post.status,
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            # 🔥 RETURN REAL ERROR FOR DEBUGGING
            return Response(
                {
                    "error": str(e),
                    "exception_type": type(e).__name__,
                    "trace": traceback.format_exc()
                },
                status=status.HTTP_400_BAD_REQUEST
            )

# -------------------------------------------------------------------
# Pipeline Create API View (POST)
# -------------------------------------------------------------------

class PipelineCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create a new sales pipeline",
        request_body=PipelineSerializer,          # WRITE
        responses={
            201: PipelineReadSerializer,           # READ
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Pipelines"],
    )
    def post(self, request):
        try:
            serializer = PipelineSerializer(
                data=request.data,
                context={"request": request},
            )
            serializer.is_valid(raise_exception=True)

            pipeline = serializer.save()

            return Response(
                PipelineReadSerializer(pipeline).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as ve:
            logger.warning(f"Pipeline validation failed: {ve.detail}")
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Pipeline Create Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# LIST PIPELINES (Left Sidebar) (GET)
# -------------------------------------------------------------------

class PipelineListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="List all pipelines for a clinic",
        responses={200: PipelineReadSerializer(many=True)},
        tags=["Pipelines"],
    )
    def get(self, request):
        try:
            clinic_id = request.query_params.get("clinic_id")
            if not clinic_id:
                raise ValidationError({"clinic_id": "This field is required"})

            pipelines = Pipeline.objects.filter(
                clinic_id=clinic_id,
                is_active=True
            )

            return Response(
                PipelineReadSerializer(pipelines, many=True).data,
                status=status.HTTP_200_OK,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Pipeline List Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# GET SINGLE PIPELINE (Canvas Load) (GET)
# -------------------------------------------------------------------


class PipelineDetailAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Get pipeline with stages, rules, and fields",
        responses={200: PipelineReadSerializer},
        tags=["Pipelines"],
    )
    def get(self, request, pipeline_id):
        try:
            pipeline = Pipeline.objects.get(id=pipeline_id)

            return Response(
                PipelineReadSerializer(pipeline).data,
                status=status.HTTP_200_OK,
            )

        except Pipeline.DoesNotExist:
            return Response(
                {"error": "Pipeline not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except Exception:
            logger.error(
                "Unhandled Pipeline Detail Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# ADD STAGE TO PIPELINE (POST)
# -------------------------------------------------------------------


class PipelineStageCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Add a new stage to a pipeline",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "pipeline_id": openapi.Schema(type=openapi.TYPE_STRING),
                "stage_name": openapi.Schema(type=openapi.TYPE_STRING),
                "stage_type": openapi.Schema(type=openapi.TYPE_STRING),
            },
            required=["pipeline_id", "stage_name", "stage_type"],
        ),
        tags=["Pipeline Stages"],
    )
    def post(self, request):
        try:
            stage = add_stage(request.data)

            return Response(
                {"id": stage.id, "stage_name": stage.stage_name},
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Stage Create Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# UPDATE STAGE (PUT)
# -------------------------------------------------------------------

class PipelineStageUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Update pipeline stage",
        tags=["Pipeline Stages"],
    )
    def put(self, request, stage_id):
        try:
            stage = PipelineStage.objects.get(id=stage_id)
            updated = update_stage(stage, request.data)

            return Response(
                {"message": "Stage updated successfully"},
                status=status.HTTP_200_OK,
            )

        except PipelineStage.DoesNotExist:
            return Response(
                {"error": "Stage not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Stage Update Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# SAVE STAGE RULES (POST)
# -------------------------------------------------------------------

class StageRuleSaveAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Save stage action rules",
        tags=["Pipeline Stages"],
    )
    def post(self, request, stage_id):
        try:
            stage = PipelineStage.objects.get(id=stage_id)
            save_stage_rules(stage, request.data.get("rules", []))

            return Response(
                {"message": "Stage rules saved"},
                status=status.HTTP_200_OK,
            )

        except PipelineStage.DoesNotExist:
            return Response(
                {"error": "Stage not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Stage Rule Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ------------------------------------------------------------------
# ADD STAGE TO PIPELINE (POST)
# -------------------------------------------------------------------

class StageFieldSaveAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Save stage data capture fields",
        tags=["Pipeline Stages"],
    )
    def post(self, request, stage_id):
        try:
            stage = PipelineStage.objects.get(id=stage_id)
            save_stage_fields(stage, request.data.get("fields", []))

            return Response(
                {"message": "Stage fields saved"},
                status=status.HTTP_200_OK,
            )

        except PipelineStage.DoesNotExist:
            return Response(
                {"error": "Stage not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Stage Field Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ------------------------------------------------------------------
# SAVE STAGE RULES (POST)
# -------------------------------------------------------------------

class StageRuleSaveAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Save stage action rules",
        tags=["Pipeline Stages"],
    )
    def post(self, request, stage_id):
        try:
            stage = PipelineStage.objects.get(id=stage_id)
            save_stage_rules(stage, request.data.get("rules", []))

            return Response(
                {"message": "Stage rules saved"},
                status=status.HTTP_200_OK,
            )

        except PipelineStage.DoesNotExist:
            return Response(
                {"error": "Stage not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Stage Rule Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# ------------------------------------------------------------------
# SAVE STAGE FIELDS (POST)
# -------------------------------------------------------------------

class StageFieldSaveAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Save stage data capture fields",
        tags=["Pipeline Stages"],
    )
    def post(self, request, stage_id):
        try:
            stage = PipelineStage.objects.get(id=stage_id)
            save_stage_fields(stage, request.data.get("fields", []))

            return Response(
                {"message": "Stage fields saved"},
                status=status.HTTP_200_OK,
            )

        except PipelineStage.DoesNotExist:
            return Response(
                {"error": "Stage not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Stage Field Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class EmailCampaignCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create Email Campaign Only",
        request_body=EmailCampaignCreateSerializer,  # ✅ FIXED
        responses={
            201: "Email Campaign Created Successfully",
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Email Campaign"],
    )
    @transaction.atomic
    def post(self, request):
        try:
            serializer = EmailCampaignCreateSerializer(data=request.data)  # ✅ FIXED
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            # 1️⃣ Create Campaign (Email Mode internally set)
            campaign = Campaign.objects.create(
                clinic_id=data["clinic"],
                campaign_name=data["campaign_name"],
                campaign_description=data["campaign_description"],
                campaign_objective=data["campaign_objective"],
                target_audience=data["target_audience"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                campaign_mode=Campaign.EMAIL,  # ✅ internally set
                selected_start=data["selected_start"],
                selected_end=data["selected_end"],
                enter_time=data["enter_time"],
                is_active=True,
            )

            created_email_configs = []

            # 2️⃣ Create Email Configs
            for email_data in data["email"]:
                email_config = CampaignEmailConfig.objects.create(
                    campaign=campaign,
                    audience_name=email_data["audience_name"],
                    subject=email_data["subject"],
                    email_body=email_data["email_body"],
                    template_name=email_data.get("template_name"),
                    sender_email=email_data["sender_email"],
                    scheduled_at=email_data.get("scheduled_at"),
                    is_active=True,
                )

                send_to_zapier({
                    "event": "email_campaign_created",
                    "campaign_id": str(campaign.id),
                    "campaign_name": campaign.campaign_name,
                    "campaign_description": campaign.campaign_description,
                    "campaign_objective": campaign.campaign_objective,
                    "target_audience": campaign.target_audience,
                    "start_date": campaign.start_date.isoformat(),
                    "end_date": campaign.end_date.isoformat(),
                    "subject": email_config.subject,
                    "email_body": email_config.email_body,
                    "sender_email": email_config.sender_email,
                    "scheduled_at": email_config.scheduled_at.isoformat() if email_config.scheduled_at else None,
                })

                created_email_configs.append({
                    "email_config_id": email_config.id,
                    "audience_name": email_config.audience_name,
                })

            return Response(
                {
                    "message": "Email campaign created successfully",
                    "campaign_id": campaign.id,
                    "emails": created_email_configs,
                },
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        except Exception:
            logger.error(
                "Email Campaign Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
# ------------------------------------------------------------------
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

# -------------------------------
# SEND SMS API
# -------------------------------
class SendSMSAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Send SMS using Twilio",
        request_body=SendSMSSerializer,
        responses={
            200: "SMS Sent Successfully",
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Twilio"],
    )
    @transaction.atomic
    def post(self, request):
        try:
            serializer = SendSMSSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            message = send_sms(
                validated_data["to"],
                validated_data["message"]
            )

            return Response(
                {
                    "message": "SMS sent successfully",
                    "sid": message.sid,
                    "status": message.status,
                },
                status=status.HTTP_200_OK,
            )

        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        except Exception:
            logger.error("Twilio SMS Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -------------------------------
# MAKE CALL API
# -------------------------------
class MakeCallAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Make outbound call using Twilio",
        request_body=MakeCallSerializer,
        responses={
            200: "Call Initiated Successfully",
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Twilio"],
    )
    @transaction.atomic
    def post(self, request):
        try:
            serializer = MakeCallSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            call = make_call(validated_data["to"])

            return Response(
                {
                    "message": "Call initiated successfully",
                    "sid": call.sid,
                    "status": call.status,
                },
                status=status.HTTP_200_OK,
            )

        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        except Exception:
            logger.error("Twilio Call Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
# ------------------------------------------------------------------
# Social Media Campaign Create API View (POST)
# -------------------------------------------------------------------

class SocialMediaCampaignCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create Social Media Campaign Only",
        request_body=SocialMediaCampaignSerializer,
        responses={
            201: "Campaign Created Successfully",
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Social Media Campaign"],
    )
    @transaction.atomic
    def post(self, request):
        try:
            print("SOCIAL DATA:", request.data)
            serializer = SocialMediaCampaignSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            data = serializer.validated_data

            mode_mapping = {
                "organic_posting": Campaign.ORGANIC,
                "paid_advertising": Campaign.PAID,
            }

            created_campaigns = []

            for mode in data["campaign_mode"]:

                campaign = Campaign.objects.create(
                    clinic_id=data["clinic"],
                    campaign_name=data["campaign_name"],
                    campaign_description=data["campaign_description"],
                    campaign_objective=data["campaign_objective"],
                    target_audience=data["target_audience"],
                    start_date=data["start_date"],
                    end_date=data["end_date"],
                    campaign_mode=mode_mapping.get(mode),
                    campaign_content=data["campaign_content"],
                    selected_start=data["start_date"],
                    selected_end=data["end_date"],
                    enter_time=data["enter_time"],
                    is_active=True,
                )

                channels = []

                for platform in data["select_ad_accounts"]:
                    CampaignSocialMediaConfig.objects.create(
                        campaign=campaign,
                        platform_name=platform,
                        is_active=True,
                    )
                    channels.append(platform)

                # 🔥 UPDATED ZAPIER PAYLOAD (Boolean Flags)
                send_to_zapier({
                    "event": "social_media_campaign_created",
                    "campaign_id": str(campaign.id),
                    "campaign_name": campaign.campaign_name,
                    "clinic_id": campaign.clinic.id,
                    "campaign_mode": campaign.campaign_mode,

                    "is_instagram": "instagram" in channels,
                    "is_facebook": "facebook" in channels,
                    "is_linkedin": "linkedin" in channels,

                    "start_date": campaign.start_date.isoformat(),
                    "end_date": campaign.end_date.isoformat(),
                    "enter_time": campaign.enter_time.strftime("%H:%M"),
                    "campaign_content": campaign.campaign_content,
                })

                created_campaigns.append({
                    "campaign_id": campaign.id,
                    "mode": mode,
                    "platforms": channels,
                })

            return Response(
                {
                    "message": "Social media campaign(s) created successfully",
                    "campaigns": created_campaigns,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            import traceback
            return Response({
                "error": str(e),
                "type": type(e).__name__,
                "trace": traceback.format_exc()
            }, status=400)


# ------------------------------------------------------------------
# Ticketcreate API View (POST)
# -------------------------------------------------------------------


class TicketCreateAPIView(APIView):

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

# ------------------------------------------------------------------
# Ticket Update API View (PUT)
# -------------------------------------------------------------------

class TicketUpdateAPIView(APIView):

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

# ------------------------------------------------------------------
# Ticket List API View (GET)
# -------------------------------------------------------------------

class TicketListAPIView(APIView):

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
        try:
            queryset = Ticket.objects.filter(is_deleted=False)

            # Filtering
            if request.query_params.get("status"):
                queryset = queryset.filter(status=request.query_params.get("status"))

            if request.query_params.get("priority"):
                queryset = queryset.filter(priority=request.query_params.get("priority"))

            if request.query_params.get("lab_id"):
                queryset = queryset.filter(lab_id=request.query_params.get("lab_id"))

            if request.query_params.get("department_id"):
                queryset = queryset.filter(department_id=request.query_params.get("department_id"))

            # Pagination
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

# ------------------------------------------------------------------
# Ticket Detail API View (GET)
# -------------------------------------------------------------------

class TicketDetailAPIView(APIView):

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

        # Prevent Swagger schema crash
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

# ------------------------------------------------------------------
# Ticket Assign for Employee API View (POST)
# -------------------------------------------------------------------

class TicketAssignAPIView(APIView):

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

            if not assigned_to_id:
                raise ValidationError("assigned_to_id is required")

            ticket.assigned_to_id = assigned_to_id
            ticket.save()

            TicketTimeline.objects.create(
                ticket=ticket,
                action="Ticket Assigned",
                done_by_id=assigned_to_id
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

# ------------------------------------------------------------------
# Ticket Status Update API View (POST)
# -------------------------------------------------------------------

class TicketStatusUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Update the status of a ticket",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["status"],
            properties={
                "status": openapi.Schema(type=openapi.TYPE_STRING)
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

            new_status = request.data.get("status")

            if not new_status:
                raise ValidationError("status field is required")

            ticket.status = new_status

            if new_status == "resolved":
                ticket.resolved_at = timezone.now()

            if new_status == "closed":
                ticket.closed_at = timezone.now()

            ticket.save()

            TicketTimeline.objects.create(
                ticket=ticket,
                action=f"Status changed to {new_status}",
                done_by=ticket.assigned_to
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


# ------------------------------------------------------------------
# Ticket Document Upload API View (POST)
# -------------------------------------------------------------------

class TicketDocumentUploadAPIView(APIView):

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

        # Prevent Swagger schema crash
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

# ------------------------------------------------------------------
# Ticket Delete API View (DELETE)
# -------------------------------------------------------------------

class TicketDeleteAPIView(APIView):

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

# ------------------------------------------------------------------
# Ticket Dashboard Count API View (GET)
# -------------------------------------------------------------------

class TicketDashboardCountAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Get ticket count grouped by status",
        responses={
            200: "Ticket count response",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def get(self, request):
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


# -------------------------------------------------------------------
# LAB CREATE API
# -------------------------------------------------------------------
class LabCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create a new lab",
        request_body=LabWriteSerializer,
        responses={
            201: LabReadSerializer,
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Labs"],
    )
    def post(self, request):
        try:
            serializer = LabWriteSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            lab = serializer.save()

            return Response(
                LabReadSerializer(lab).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )


# -------------------------------------------------------------------
# LAB LIST API
# -------------------------------------------------------------------
class LabListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="List all active labs",
        responses={200: LabReadSerializer(many=True)},
        tags=["Labs"],
    )
    def get(self, request):

        labs = Lab.objects.filter(
            is_deleted=False,
            is_active=True
        )

        return Response(
            LabReadSerializer(labs, many=True).data,
            status=status.HTTP_200_OK,
        )


# -------------------------------------------------------------------
# LAB UPDATE API
# -------------------------------------------------------------------
class LabUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Update lab",
        request_body=LabWriteSerializer,
        responses={
            200: LabReadSerializer,
            404: "Lab not found",
        },
        tags=["Labs"],
    )
    def put(self, request, lab_id):

        lab = get_object_or_404(
            Lab,
            id=lab_id,
            is_deleted=False
        )

        serializer = LabWriteSerializer(
            lab,
            data=request.data,
            partial=True
        )

        serializer.is_valid(raise_exception=True)

        updated_lab = serializer.save()

        return Response(
            LabReadSerializer(updated_lab).data,
            status=status.HTTP_200_OK,
        )


# -------------------------------------------------------------------
# LAB SOFT DELETE API
# -------------------------------------------------------------------
class LabSoftDeleteAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Soft delete lab",
        tags=["Labs"],
    )
    def delete(self, request, lab_id):

        lab = get_object_or_404(
            Lab,
            id=lab_id,
            is_deleted=False
        )

        lab.is_deleted = True
        lab.is_active = False
        lab.save()

        return Response(
            {"message": "Lab deleted successfully"},
            status=status.HTTP_200_OK,
        )

# -------------------------------------------------------------------
# TEMPLATE LIST API (GET)
# -------------------------------------------------------------------

class TemplateListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="List Templates by type (mail, sms, whatsapp)",
    )
    def get(self, request, template_type):
        try:
            if template_type == "mail":
                templates = TemplateMail.objects.filter(is_deleted=False)
                serializer = TemplateMailReadSerializer(templates, many=True)

            elif template_type == "sms":
                templates = TemplateSMS.objects.filter(is_deleted=False)
                serializer = TemplateSMSReadSerializer(templates, many=True)

            elif template_type == "whatsapp":
                templates = TemplateWhatsApp.objects.filter(is_deleted=False)
                serializer = TemplateWhatsAppReadSerializer(templates, many=True)

            else:
                raise ValidationError(
                    "Invalid template type. Allowed values: mail, sms, whatsapp."
                )

            return Response(serializer.data, status=status.HTTP_200_OK)

        except ValidationError as validation_error:
            logger.warning(f"Template List validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Template List Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -------------------------------------------------------------------
# TEMPLATE DETAIL API (GET)
# -------------------------------------------------------------------
class TemplateDetailAPIView(APIView):

    def get(self, request, template_type, template_id):
        try:

            if template_type == "mail":
                template_instance = TemplateMail.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "Mail template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                serializer = TemplateMailReadSerializer(template_instance)

            elif template_type == "sms":
                template_instance = TemplateSMS.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "SMS template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                serializer = TemplateSMSReadSerializer(template_instance)

            elif template_type == "whatsapp":
                template_instance = TemplateWhatsApp.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "WhatsApp template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                serializer = TemplateWhatsAppReadSerializer(template_instance)

            else:
                raise ValidationError(
                    "Invalid template type. Allowed values: mail, sms, whatsapp."
                )

            return Response(serializer.data, status=status.HTTP_200_OK)

        except ValidationError as validation_error:
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# TEMPLATE CREATE API (POST)
# -------------------------------------------------------------------

class TemplateCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create Template (mail, sms, whatsapp)",
    )
    def post(self, request, template_type):
        try:
            if template_type == "mail":
                write_serializer = TemplateMailSerializer(data=request.data)
                read_serializer_class = TemplateMailReadSerializer

            elif template_type == "sms":
                write_serializer = TemplateSMSSerializer(data=request.data)
                read_serializer_class = TemplateSMSReadSerializer

            elif template_type == "whatsapp":
                write_serializer = TemplateWhatsAppSerializer(data=request.data)
                read_serializer_class = TemplateWhatsAppReadSerializer

            else:
                raise ValidationError(
                    "Invalid template type. Allowed values: mail, sms, whatsapp."
                )

            write_serializer.is_valid(raise_exception=True)
            template_instance = write_serializer.save()

            return Response(
                read_serializer_class(template_instance).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as validation_error:
            logger.warning(f"Template Create validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Template Create Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# TEMPLATE UPDATE API (PUT)
# -------------------------------------------------------------------

class TemplateUpdateAPIView(APIView):

    def put(self, request, template_type, template_id):
        try:
            if template_type == "mail":
                template_instance = TemplateMail.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "Mail template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                serializer = TemplateMailSerializer(
                    template_instance,
                    data=request.data,
                    partial=True
                )

                read_serializer_class = TemplateMailReadSerializer

            elif template_type == "sms":
                template_instance = TemplateSMS.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "SMS template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                serializer = TemplateSMSSerializer(
                    template_instance,
                    data=request.data,
                    partial=True
                )

                read_serializer_class = TemplateSMSReadSerializer

            elif template_type == "whatsapp":
                template_instance = TemplateWhatsApp.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "WhatsApp template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                serializer = TemplateWhatsAppSerializer(
                    template_instance,
                    data=request.data,
                    partial=True
                )

                read_serializer_class = TemplateWhatsAppReadSerializer

            else:
                raise ValidationError(
                    "Invalid template type. Allowed values: mail, sms, whatsapp."
                )

            serializer.is_valid(raise_exception=True)
            updated_template = serializer.save()

            return Response(
                read_serializer_class(updated_template).data,
                status=status.HTTP_200_OK,
            )

        except ValidationError as validation_error:
            logger.warning(f"Template Update validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Template Update Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -------------------------------------------------------------------
# TEMPLATE SOFT DELETE API (DELETE)
# -------------------------------------------------------------------

class TemplateDeleteAPIView(APIView):

    def delete(self, request, template_type, template_id):
        try:
            if template_type == "mail":
                template_instance = TemplateMail.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

            elif template_type == "sms":
                template_instance = TemplateSMS.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

            elif template_type == "whatsapp":
                template_instance = TemplateWhatsApp.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

            else:
                raise ValidationError(
                    "Invalid template type. Allowed values: mail, sms, whatsapp."
                )

            if not template_instance:
                return Response(
                    {"error": "Template not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            template_instance.is_deleted = True
            template_instance.save()

            return Response(
                {"message": "Template deleted successfully."},
                status=status.HTTP_200_OK,
            )

        except ValidationError as validation_error:
            logger.warning(f"Template Delete validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Template Delete Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class LinkedInLoginAPIView(APIView):
    def get(self, request):
        auth_url = (
            "https://www.linkedin.com/oauth/v2/authorization"
            "?response_type=code"
            f"&client_id={settings.LINKEDIN_CLIENT_ID}"
            f"&redirect_uri={settings.LINKEDIN_REDIRECT_URI}"
            "&scope=openid%20profile%20email"
            "&prompt=login"
        )
        return redirect(auth_url)    


class LinkedInCallbackAPIView(APIView):
    def get(self, request):
        code = request.GET.get("code")

        token_url = "https://www.linkedin.com/oauth/v2/accessToken"

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        }

        response = requests.post(token_url, data=data)
        token_data = response.json()

        access_token = token_data.get("access_token")

        if access_token:
            # Demo storage
            request.session["linkedin_token"] = access_token

        # Redirect back to frontend with success flag
        return HttpResponseRedirect(
            f"{settings.FRONTEND_URL}?linkedin=connected"
        )

class LinkedInStatusAPIView(APIView):
    def get(self, request):
        return Response({
            "connected": bool(request.session.get("linkedin_token"))
        })

class FacebookLoginAPIView(APIView):
    def get(self, request):
        state = secrets.token_urlsafe(16)
        request.session["facebook_state"] = state

        auth_url = (
            "https://www.facebook.com/v19.0/dialog/oauth"
            "?response_type=code"
            f"&client_id={settings.FACEBOOK_CLIENT_ID}"
            f"&redirect_uri={settings.FACEBOOK_REDIRECT_URI}"
            "&scope=email,public_profile"
            f"&state={state}"
            "&auth_type=rerequest"
        )

        return redirect(auth_url)

class FacebookCallbackAPIView(APIView):
    def get(self, request):
        code = request.GET.get("code")

        if not code:
            return Response({"error": "No code received"})

        token_url = "https://graph.facebook.com/v19.0/oauth/access_token"

        params = {
            "client_id": settings.FACEBOOK_CLIENT_ID,
            "client_secret": settings.FACEBOOK_CLIENT_SECRET,
            "redirect_uri": settings.FACEBOOK_REDIRECT_URI,
            "code": code,
        }

        response = requests.get(token_url, params=params)
        data = response.json()

        print("FB TOKEN RESPONSE:", data)

        if "access_token" not in data:
            return Response(data)  # show real error

        request.session["facebook_token"] = data["access_token"]

        return HttpResponseRedirect(
            f"{settings.FRONTEND_URL}?facebook=connected"
        )


class FacebookStatusAPIView(APIView):
    def get(self, request):
        return Response({
            "connected": bool(request.session.get("facebook_token"))
        })
