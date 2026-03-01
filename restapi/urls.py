"""
Main API URL Configuration

Structure:
- Clinics
- Employees / Users
- Leads
- Campaigns
- Pipelines
- Tickets

Each section is grouped logically for clarity and maintainability.
"""

from django.urls import path

from .views import (

    # ==================================================
    # Clinic APIs
    # ==================================================
    ClinicCreateAPIView,
    ClinicUpdateAPIView,
    GetClinicView,

    # ==================================================
    # Employee / User APIs
    # ==================================================
    ClinicEmployeesAPIView,
    EmployeeCreateAPIView,
    UserCreateAPIView,

    # ==================================================
    # Lead APIs
    # ==================================================
    LeadCreateAPIView,
    LeadUpdateAPIView,
    LeadListAPIView,
    LeadGetAPIView,
    LeadActivateAPIView,
    LeadInactivateAPIView,
    LeadSoftDeleteAPIView,
    LeadEmailAPIView,

    # ==================================================
    # Lead Notes APIs
    # ==================================================
    LeadNoteCreateAPIView,
    LeadNoteUpdateAPIView,
    LeadNoteDeleteAPIView,
    LeadNoteListAPIView,


    # ==================================================
    # Campaign APIs
    # ==================================================
    CampaignCreateAPIView,
    CampaignUpdateAPIView,
    CampaignListAPIView,
    CampaignGetAPIView,
    CampaignActivateAPIView,
    CampaignInactivateAPIView,
    CampaignSoftDeleteAPIView,
    SocialMediaCampaignCreateAPIView,
    EmailCampaignCreateAPIView,
    CampaignZapierCallbackAPIView,
    MailchimpWebhookAPIView,
    SendSMSAPIView,
    MakeCallAPIView,
    TwilioMessageListAPIView,
    TwilioCallListAPIView,
    
    # ==================================================
    # Sales Pipeline APIs
    # ==================================================
    PipelineCreateAPIView,
    PipelineListAPIView,
    PipelineDetailAPIView,
    PipelineStageCreateAPIView,
    PipelineStageUpdateAPIView,
    StageRuleSaveAPIView,
    StageFieldSaveAPIView,

    # ==================================================
    # Ticket APIs
    # ==================================================
    TicketListAPIView,
    TicketDetailAPIView,
    TicketCreateAPIView,
    TicketUpdateAPIView,
    TicketAssignAPIView,
    TicketStatusUpdateAPIView,
    TicketDocumentUploadAPIView,
    TicketDeleteAPIView,
    TicketDashboardCountAPIView,

    
    # ==================================================
    # Lab APIs
    # ==================================================

    LabListAPIView,
    LabCreateAPIView,
    LabUpdateAPIView,
    LabSoftDeleteAPIView,

    # ==================================================
    # Template APIs
    # ==================================================
    TemplateListAPIView,
    TemplateCreateAPIView,
    TemplateUpdateAPIView,
    TemplateDeleteAPIView,
    TemplateDetailAPIView,
    TemplateDocumentUploadAPIView,

    LinkedInLoginAPIView,
    LinkedInCallbackAPIView,
    LinkedInStatusAPIView,
    FacebookLoginAPIView,
    FacebookCallbackAPIView,
    FacebookStatusAPIView,
)

urlpatterns = [

# ==================================================
# CLINIC APIs
# ==================================================

    # Create a new clinic
    path("clinics/", ClinicCreateAPIView.as_view(), name="clinic-create"),

    # Update existing clinic (full update)
    path("clinics/<int:clinic_id>/", ClinicUpdateAPIView.as_view(), name="clinic-update"),

    # Get clinic details by ID
    path("clinics/<int:clinic_id>/detail/", GetClinicView.as_view(), name="clinic-get"),


# ==================================================
# EMPLOYEE / USER APIs
# ==================================================

    # Get all employees under a specific clinic
    path(
        "clinics/<int:clinic_id>/employees/",
        ClinicEmployeesAPIView.as_view(),
        name="clinic-employees",
    ),

    # Create employee
    path("employees/", EmployeeCreateAPIView.as_view(), name="employee-create"),

    # Create system user
    path("users/", UserCreateAPIView.as_view(), name="user-create"),


# ==================================================
# LEAD APIs
# ==================================================

    # Create lead
    path("leads/", LeadCreateAPIView.as_view(), name="lead-create"),

    # Update lead (full update)
    path("leads/<uuid:lead_id>/update/", LeadUpdateAPIView.as_view(), name="lead-update"),

    # List all leads
    path("leads/list/", LeadListAPIView.as_view(), name="lead-list"),

    # Get single lead details
    path("leads/<uuid:lead_id>/", LeadGetAPIView.as_view(), name="lead-get"),

    # Activate lead
    path("leads/<uuid:lead_id>/activate/", LeadActivateAPIView.as_view(), name="lead-activate"),

    # Inactivate lead
    path("leads/<uuid:lead_id>/inactivate/", LeadInactivateAPIView.as_view(), name="lead-inactivate"),

    # Soft delete lead
    path("leads/<uuid:lead_id>/delete/", LeadSoftDeleteAPIView.as_view(), name="lead-soft-delete"),

    path("lead-email/", LeadEmailAPIView.as_view(), name="lead-email"),
    
    path("twilio/send-sms/", SendSMSAPIView.as_view()),
    path("twilio/make-call/", MakeCallAPIView.as_view()),

# GET: Retrieve SMS
# Example:
# /api/twilio/sms/?lead_uuid=<lead_uuid>
# lead_uuid is REQUIRED
path("twilio/sms/", TwilioMessageListAPIView.as_view(), name="twilio-sms-list"),

# GET: Retrieve Calls
# Example:
# /api/twilio/calls/?lead_uuid=<lead_uuid>
# lead_uuid is REQUIRED
path("twilio/calls/", TwilioCallListAPIView.as_view(), name="twilio-call-list"),  

# ==================================================
# LEAD NOTES APIs
# ==================================================

# Create a new note for a lead
path("leads/notes/", LeadNoteCreateAPIView.as_view(), name="lead-note-create"),

# Update existing note (partial update supported)
path("leads/notes/<uuid:note_id>/update/", LeadNoteUpdateAPIView.as_view(), name="lead-note-update"),

# Soft delete a note
path("leads/notes/<uuid:note_id>/delete/", LeadNoteDeleteAPIView.as_view(), name="lead-note-delete"),

# List all notes for a specific lead
path("leads/<uuid:lead_id>/notes/", LeadNoteListAPIView.as_view(), name="lead-note-list"),


# ==================================================
# CAMPAIGN APIs
# ==================================================

    # Create campaign
    path("campaigns/", CampaignCreateAPIView.as_view(), name="campaign-create"),

    # Update campaign
    path("campaigns/<uuid:campaign_id>/update/", CampaignUpdateAPIView.as_view(), name="campaign-update"),

    # List campaigns
    path("campaigns/list/", CampaignListAPIView.as_view(), name="campaign-list"),

    # Get campaign details
    path("campaigns/<uuid:campaign_id>/", CampaignGetAPIView.as_view(), name="campaign-get"),

    # Activate campaign
    path("campaigns/<uuid:campaign_id>/activate/", CampaignActivateAPIView.as_view(), name="campaign-activate"),

    # Inactivate campaign
    path("campaigns/<uuid:campaign_id>/inactivate/", CampaignInactivateAPIView.as_view(), name="campaign-inactivate"),

    # Soft delete campaign
    path("campaigns/<uuid:campaign_id>/delete/", CampaignSoftDeleteAPIView.as_view(), name="campaign-soft-delete"),

    # Create social media campaign
    path(
        "social-media-campaign/create/",
        SocialMediaCampaignCreateAPIView.as_view(),
        name="social-media-campaign-create",
    ),
    # Create email campaign
    path(
        "campaigns/email/create/",
        EmailCampaignCreateAPIView.as_view(),
        name="email-campaign-create",
    ),

    path(
    "campaigns/zapier-callback/",
    CampaignZapierCallbackAPIView.as_view(),
    name="campaign-zapier-callback",
),
    # Mailchimp webhook receiver
    path(
        "mailchimp/webhook/",
        MailchimpWebhookAPIView.as_view(),
        name="mailchimp-webhook",
    ),
    
    path("twilio/send-sms/", SendSMSAPIView.as_view()),
    path("twilio/make-call/", MakeCallAPIView.as_view()),


    # GET: Retrieve SMS
# Example:
# /api/twilio/sms/?lead_uuid=<lead_uuid>
# lead_uuid is REQUIRED
path("twilio/sms/", TwilioMessageListAPIView.as_view(), name="twilio-sms-list"),

# GET: Retrieve Calls
# Example:
# /api/twilio/calls/?lead_uuid=<lead_uuid>
# lead_uuid is REQUIRED
path("twilio/calls/", TwilioCallListAPIView.as_view(), name="twilio-call-list"),  




    

# ==================================================
# SALES PIPELINE APIs
# ==================================================

    # Create pipeline
    path("pipelines/create/", PipelineCreateAPIView.as_view(), name="pipeline-create"),

    # List pipelines
    path("pipelines/", PipelineListAPIView.as_view(), name="pipeline-list"),

    # Get pipeline with stages
    path("pipelines/<uuid:pipeline_id>/", PipelineDetailAPIView.as_view(), name="pipeline-detail"),

    # Create pipeline stage
    path("pipelines/stages/create/", PipelineStageCreateAPIView.as_view(), name="pipeline-stage-create"),

    # Update pipeline stage
    path("pipelines/stages/<uuid:stage_id>/update/", PipelineStageUpdateAPIView.as_view(), name="pipeline-stage-update"),

    # Save stage rules
    path("pipelines/stages/<uuid:stage_id>/rules/", StageRuleSaveAPIView.as_view(), name="pipeline-stage-rules-save"),

    # Save stage fields (data capture)
    path("pipelines/stages/<uuid:stage_id>/fields/", StageFieldSaveAPIView.as_view(), name="pipeline-stage-fields-save"),


# ==================================================
# TICKET APIs
# ==================================================

    # List tickets (with filters + pagination)
    path("tickets/", TicketListAPIView.as_view(), name="ticket-list"),

    # Get single ticket details
    path("tickets/<uuid:ticket_id>/", TicketDetailAPIView.as_view(), name="ticket-detail"),

    # Create new ticket
    path("tickets/create/", TicketCreateAPIView.as_view(), name="ticket-create"),

    # Update ticket (full update)
    path("tickets/<uuid:ticket_id>/update/", TicketUpdateAPIView.as_view(), name="ticket-update"),

    # Assign ticket to employee
    path("tickets/<uuid:ticket_id>/assign/", TicketAssignAPIView.as_view(), name="ticket-assign"),

    # Update ticket status
    path("tickets/<uuid:ticket_id>/status/", TicketStatusUpdateAPIView.as_view(), name="ticket-status-update"),

    # Upload document to ticket
    path("tickets/<uuid:ticket_id>/documents/", TicketDocumentUploadAPIView.as_view(), name="ticket-document-upload"),

    # Soft delete ticket
    path("tickets/<uuid:ticket_id>/delete/", TicketDeleteAPIView.as_view(), name="ticket-delete"),

    # Dashboard count for tickets
    path("tickets/dashboard-count/", TicketDashboardCountAPIView.as_view(), name="ticket-dashboard-count"),

# ==================================================
# LAB APIs
# ==================================================

# List all active labs (used for dropdown selection in ticket creation)
path(
    "labs/", LabListAPIView.as_view(), name="lab-list"),

# Create a new lab under a clinic
path(
    "labs/create/", LabCreateAPIView.as_view(), name="lab-create"),

# Update existing lab details (Full Update using PUT)
path(
    "labs/<uuid:lab_id>/update/", LabUpdateAPIView.as_view(), name="lab-update"),

# Soft delete lab (marks lab as inactive and deleted)
path(
    "labs/<uuid:lab_id>/delete/", LabSoftDeleteAPIView.as_view(), name="lab-delete" ),


# ==================================================
# TEMPLATE APIs
# ==================================================
    
    path(
        "templates/<str:template_type>/<uuid:template_id>/documents/",
        TemplateDocumentUploadAPIView.as_view(),
        name="template-document-upload",
    ),

    # List templates by type (mail / sms / whatsapp)
    path(
        "templates/<str:template_type>/", TemplateListAPIView.as_view(), name="template-list" ),

    # Get single template by ID
    path( "templates/<str:template_type>/<uuid:template_id>/", TemplateDetailAPIView.as_view(),
    name="template-detail"),

    # Create template by type
    path("templates/<str:template_type>/create/", TemplateCreateAPIView.as_view(), name="template-create"),

    # Update template by type
    path(
        "templates/<str:template_type>/<uuid:template_id>/update/", TemplateUpdateAPIView.as_view(), 
        name="template-update",
    ),

    # Soft delete template by type
    path(
        "templates/<str:template_type>/<uuid:template_id>/delete/", TemplateDeleteAPIView.as_view(),
        name="template-delete",
    ),

    # LinkedIn Integration
    path("linkedin/login/", LinkedInLoginAPIView.as_view()),
    path("linkedin/callback/", LinkedInCallbackAPIView.as_view()),
    path("linkedin/status/", LinkedInStatusAPIView.as_view()),

    path("facebook/login/", FacebookLoginAPIView.as_view()),
    path("facebook/callback/", FacebookCallbackAPIView.as_view()),
    path("facebook/status/", FacebookStatusAPIView.as_view()),

]
