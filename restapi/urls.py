from django.urls import path

from .views import (

    # =========================
    # Clinic
    # =========================
    ClinicCreateAPIView,
    ClinicUpdateAPIView,
    GetClinicView,

    # =========================
    # Employee / User
    # =========================
    ClinicEmployeesAPIView,
    EmployeeCreateAPIView,
    UserCreateAPIView,

    # =========================
    # Leads
    # =========================
    LeadCreateAPIView,
    LeadUpdateAPIView,
    LeadListAPIView,
    LeadGetAPIView,
    LeadActivateAPIView,
    LeadInactivateAPIView,
    LeadSoftDeleteAPIView,


    # =========================
    # Campaigns
    # =========================
    CampaignCreateAPIView,
    CampaignUpdateAPIView,
    CampaignListAPIView,
    CampaignGetAPIView,
    CampaignActivateAPIView,
    CampaignInactivateAPIView,
    CampaignSoftDeleteAPIView,

    PipelineCreateAPIView,
    PipelineListAPIView,
    PipelineDetailAPIView,

    PipelineStageCreateAPIView,
    PipelineStageUpdateAPIView,

    StageRuleSaveAPIView,
    StageFieldSaveAPIView,
    
    
)

urlpatterns = [

# ==================================================
# Clinic APIs
# ==================================================

    # Create Clinic (POST)
    path("clinics", ClinicCreateAPIView.as_view(), name="clinic-create"),

    # Update Clinic by ID (PUT)
    path("clinics/<int:clinic_id>/", ClinicUpdateAPIView.as_view(), name="clinic-update"),

    # Get Clinic by ID (GET)
    path("get_clinic/<int:clinic_id>/", GetClinicView.as_view(), name="clinic-get"),

# ==================================================
# Employee / User APIs
# ==================================================

    # Get Employees under a Clinic (GET)
    path(
        "clinics/<int:clinic_id>/employees/",
        ClinicEmployeesAPIView.as_view(),
        name="clinic-employees"
    ),

    # Create Employee (POST)
    path("employees/", EmployeeCreateAPIView.as_view(), name="employee-create"),

    # Create User (POST)
    path("users/", UserCreateAPIView.as_view(), name="user-create"),

# ==================================================
# Lead APIs
# ==================================================

    # Create Lead (POST)
    path(
        "leads/",
        LeadCreateAPIView.as_view(),
        name="lead-create"
    ),

    # Update Lead (PUT)
    path(
        "leads/<uuid:lead_id>/update/",
        LeadUpdateAPIView.as_view(),
        name="lead-update"
    ),

    # Get All Leads (GET)
    path(
        "leads/list/",
        LeadListAPIView.as_view(),
        name="lead-list"
    ),

    # Get Lead by ID (GET)
    path(
        "leads/<uuid:lead_id>/",
        LeadGetAPIView.as_view(),
        name="lead-get"
    ),

    # Activate Lead (POST)
    path(
        "leads/<uuid:lead_id>/activate/",
        LeadActivateAPIView.as_view(),
        name="lead-activate"
    ),

    # Inactivate Lead (PATCH)
    path(
        "leads/<uuid:lead_id>/inactivate/",
        LeadInactivateAPIView.as_view(),
        name="lead-inactivate"
    ),

    # Soft Delete Lead (PATCH / DELETE)
    path(
        "leads/<uuid:lead_id>/delete/",
        LeadSoftDeleteAPIView.as_view(),
        name="lead-soft-delete"
    ),


# ==================================================
# Campaign APIs
# ==================================================

    # Create Campaign (POST)
    path(
        "campaigns/",
        CampaignCreateAPIView.as_view(),
        name="campaign-create"
    ),

    # ✅ Update Campaign (PUT)
    path(
        "campaigns/<uuid:campaign_id>/update/",
        CampaignUpdateAPIView.as_view(),
        name="campaign-update"
    ),


    # Get All Campaigns (GET)
    path(
        "campaigns/list/",
        CampaignListAPIView.as_view(),
        name="campaign-list"
    ),

    # Get Campaign by ID (GET)
    path(
        "campaigns/<uuid:campaign_id>/",
        CampaignGetAPIView.as_view(),
        name="campaign-get"
    ),

    # Activate Campaign (POST)
    path(
        "campaigns/<uuid:campaign_id>/activate/",
        CampaignActivateAPIView.as_view(),
        name="campaign-activate"
    ),

    # Inactivate Campaign (PATCH)
    path(
        "campaigns/<uuid:campaign_id>/inactivate/",
        CampaignInactivateAPIView.as_view(),
        name="campaign-inactivate"
    ),

    # Soft Delete Campaign (PATCH / DELETE)
    path(
        "campaigns/<uuid:campaign_id>/delete/",
        CampaignSoftDeleteAPIView.as_view(),
        name="campaign-soft-delete"
    ),

    
   # ============================
    # PIPELINES
    # ============================

    # Create pipeline (popup save)
    path(
        "pipelines/create/",
        PipelineCreateAPIView.as_view(),
        name="pipeline-create",
    ),

    # List pipelines (left sidebar)
    path(
        "pipelines/",
        PipelineListAPIView.as_view(),
        name="pipeline-list",
    ),

    # Get single pipeline with stages
    path(
        "pipelines/<uuid:pipeline_id>/",
        PipelineDetailAPIView.as_view(),
        name="pipeline-detail",
    ),

    # ============================
    # PIPELINE STAGES
    # ============================

    # Add stage to pipeline
    path(
        "pipelines/stages/create/",
        PipelineStageCreateAPIView.as_view(),
        name="pipeline-stage-create",
    ),

    # Update stage (right panel save)
    path(
        "pipelines/stages/<uuid:stage_id>/update/",
        PipelineStageUpdateAPIView.as_view(),
        name="pipeline-stage-update",
    ),

    # ============================
    # STAGE RULES (ACTIONS)
    # ============================

    # Save stage rules
    path(
        "pipelines/stages/<uuid:stage_id>/rules/",
        StageRuleSaveAPIView.as_view(),
        name="pipeline-stage-rules-save",
    ),

    # ============================
    # STAGE DATA CAPTURE
    # ============================

    # Save stage fields
    path(
        "pipelines/stages/<uuid:stage_id>/fields/",
        StageFieldSaveAPIView.as_view(),
        name="pipeline-stage-fields-save",
    ),

]
