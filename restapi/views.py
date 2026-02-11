import traceback
import logging


from django.shortcuts import get_object_or_404

from drf_yasg import openapi

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from drf_yasg.utils import swagger_auto_schema

from restapi.services.zapier_service import send_to_zapier
from restapi.models import CampaignSocialMediaConfig

from restapi.models import Clinic
from restapi.serializers.clinic import (
    ClinicSerializer,
    ClinicReadSerializer,
)

from restapi.models import employee
from restapi.serializers.employee import (
    EmployeeCreateSerializer,
    EmployeeReadSerializer,
    UserCreateSerializer,
)
from django.db import transaction

from .models import Lead, Campaign

from restapi.models import Pipeline, PipelineStage
from restapi.services.pipeline_service import (
    add_stage,
    update_stage,
    save_stage_rules,
    save_stage_fields,
)
from restapi.serializers.lead_serializer import (
    LeadSerializer,
    LeadReadSerializer,
)


from restapi.serializers.campaign_serializer import (
    CampaignSerializer,
    CampaignReadSerializer,
    SocialMediaCampaignSerializer,
)

from restapi.serializers.pipeline_serializer import (
    PipelineSerializer,
    PipelineReadSerializer,
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
        print("🚀 STEP 1: LeadCreateAPIView HIT")

        try:
            print("📦 STEP 2: Incoming request data:")
            print(request.data)

            serializer = LeadSerializer(
                data=request.data,
                context={"request": request},
            )

            print("🧪 STEP 3: Serializer initialized")

            serializer.is_valid(raise_exception=True)
            print("✅ STEP 4: Serializer validated successfully")

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
            print("❌ VALIDATION ERROR OCCURRED")
            print(ve.detail)

            logger.warning(f"Lead validation failed: {ve.detail}")

            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            print("🔥 UNHANDLED EXCEPTION OCCURRED 🔥")
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
            # ✅ fetch existing lead
            lead = Lead.objects.get(id=lead_id)

            # ✅ PUT = full update (instance + data)
            serializer = LeadSerializer(
                lead,
                data=request.data,
                context={"request": request}
            )

            serializer.is_valid(raise_exception=True)

            # ✅ calls update_lead()
            updated_lead = serializer.save()

            # 🔔 ZAPIER
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
        operation_description="Get all leads",
        responses={200: LeadReadSerializer(many=True)},
        tags=["Leads"]
    )
    def get(self, request):
        leads = Lead.objects.filter().order_by("-created_at")

        return Response(
            LeadReadSerializer(leads, many=True).data,
            status=status.HTTP_200_OK
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

    # ✅ NOW DEFINED
    "channels": channels,

    "start_date": campaign.start_date.isoformat() if campaign.start_date else None,
    "end_date": campaign.end_date.isoformat() if campaign.end_date else None,

    "selected_start": (
        campaign.selected_start.isoformat()
        if campaign.selected_start else None
    ),
    "selected_end": (
        campaign.selected_end.isoformat()
        if campaign.selected_end else None
    ),

    "enter_time": (
        campaign.enter_time.strftime("%H:%M")
        if campaign.enter_time else None
    ),

    "is_active": campaign.is_active,
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
                "event": "campaign_updated",
                "campaign_id": str(updated_campaign.id),
                "campaign_name": updated_campaign.campaign_name,
                "clinic_id": updated_campaign.clinic.id,
                "campaign_mode": updated_campaign.campaign_mode,

                "start_date": (
                    updated_campaign.start_date.isoformat()
                    if updated_campaign.start_date else None
                ),
                "end_date": (
                    updated_campaign.end_date.isoformat()
                    if updated_campaign.end_date else None
                ),
                "selected_start": (
                    updated_campaign.selected_start.isoformat()
                    if updated_campaign.selected_start else None
                ),
                "selected_end": (
                    updated_campaign.selected_end.isoformat()
                    if updated_campaign.selected_end else None
                ),
                "enter_time": (
                    updated_campaign.enter_time.strftime("%H:%M")
                    if updated_campaign.enter_time else None
                ),
                "is_active": updated_campaign.is_active,
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
# UPDATE STAGE (Right Panel Save) (PUT)
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

        except Exception:
            logger.error(
                "Social Media Campaign Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
