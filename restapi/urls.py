"""
Main API URL Configuration — restapi/urls.py

Sections:
  1.  Clinic
  2.  Employee / User
  3.  Lead
  4.  Lead Notes
  5.  Twilio (SMS + Calls)
  6.  Campaign
  7.  Sales Pipeline
  8.  Ticket
  9.  Lab
  10. Template
  11. Mail Insights          ← Zapier webhook receiver + KPI getter + Reset
  12. Interaction Counts     ← CommunicationChart real data
  13. Debug                  ← Temporary Twilio status checker
  14. Social Auth (LinkedIn + Facebook)
  15. Image Upload
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
    EmployeeUpdateAPIView,

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
    LeadMailListAPIView,

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
    CampaignFacebookInsightsAPIView,
    FacebookDebugAPIView,

    # ==================================================
    # Twilio APIs
    # ==================================================
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

    # ==================================================
    # Social Auth
    # ==================================================
    LinkedInLoginAPIView,
    LinkedInCallbackAPIView,
    LinkedInStatusAPIView,
    FacebookLoginAPIView,
    FacebookCallbackAPIView,
    FacebookStatusAPIView,

    # ==================================================
    # Image Upload
    # ==================================================
    ImageUploadAPIView,

    # ==================================================
    # Mail Insights (Zapier → Django cache → Dashboard KPIs)
    # FIXED: MailInsightsReceiveAPIView now accumulates counts
    #        instead of overwriting — appointments_booked never
    #        gets wiped when a lead_created event fires.
    # ==================================================
    MailInsightsReceiveAPIView,    # POST  /api/mail-insights/
    MailInsightsGetAPIView,        # GET   /api/mail-insights/get/
    MailInsightsResetAPIView,      # POST  /api/mail-insights/reset/

    # ==================================================
    # Interaction Counts (CommunicationChart real data)
    # Email→SMS→Call→WhatsApp→Chatbot
    # ==================================================
    InteractionCountsAPIView,      # GET   /api/interactions/counts/

    # ==================================================
    # Debug — temporary, remove after confirming call statuses
    # Open: http://localhost:8000/api/debug/twilio-status/
    # ==================================================
    TwilioDebugAPIView,            # GET   /api/debug/twilio-status/
    MailInsightsDebugAPIView,      # GET   /api/debug/mail-insights-log/

    # In the Campaign APIs import block, add these two:
   CampaignMailchimpInsightsAPIView,
   MailchimpInsightsCallbackAPIView,

   GoHighLevelLeadWebhookAPIView,
  FBCampaignListAPIView,
  FBCampaignInsightsAPIView,
  FBCampaignCreateAPIView,

            # ==================================================
# Reputation APIs
# ==================================================
ReviewRequestCreateAPIView,
ReviewRequestListAPIView,
ReviewRequestDetailAPIView,
ReviewListAPIView,
ReputationDashboardAPIView,
ReviewCreateAPIView,

)





urlpatterns = [

    # ==================================================
    # CLINIC APIs
    # ==================================================
    path("clinics/",                        ClinicCreateAPIView.as_view(),    name="clinic-create"),
    path("clinics/<int:clinic_id>/",        ClinicUpdateAPIView.as_view(),    name="clinic-update"),
    path("clinics/<int:clinic_id>/detail/", GetClinicView.as_view(),          name="clinic-get"),

    # ==================================================
    # EMPLOYEE / USER APIs
    # ==================================================
    path("clinics/<int:clinic_id>/employees/",       ClinicEmployeesAPIView.as_view(),  name="clinic-employees"),
    path("employees/",                               EmployeeCreateAPIView.as_view(),   name="employee-create"),
    path("employees/<int:employee_id>/update/",      EmployeeUpdateAPIView.as_view(),   name="employee-update"),
    path("users/",                                   UserCreateAPIView.as_view(),       name="user-create"),

    # ==================================================
    # LEAD APIs
    # ==================================================
    path("leads/",                           LeadCreateAPIView.as_view(),      name="lead-create"),
    path("leads/<uuid:lead_id>/update/",     LeadUpdateAPIView.as_view(),      name="lead-update"),
    path("leads/list/",                      LeadListAPIView.as_view(),        name="lead-list"),
    path("leads/<uuid:lead_id>/",            LeadGetAPIView.as_view(),         name="lead-get"),
    path("leads/<uuid:lead_id>/activate/",   LeadActivateAPIView.as_view(),    name="lead-activate"),
    path("leads/<uuid:lead_id>/inactivate/", LeadInactivateAPIView.as_view(),  name="lead-inactivate"),
    path("leads/<uuid:lead_id>/delete/",     LeadSoftDeleteAPIView.as_view(),  name="lead-soft-delete"),
    path("lead-email/",                      LeadEmailAPIView.as_view(),       name="lead-email"),
    path("lead-mail/",                       LeadMailListAPIView.as_view(),    name="lead-mail-list"),

    # ==================================================
    # LEAD NOTES APIs
    # ==================================================
    path("leads/notes/",                            LeadNoteCreateAPIView.as_view(), name="lead-note-create"),
    path("leads/notes/<uuid:note_id>/update/",      LeadNoteUpdateAPIView.as_view(), name="lead-note-update"),
    path("leads/notes/<uuid:note_id>/delete/",      LeadNoteDeleteAPIView.as_view(), name="lead-note-delete"),
    path("leads/<uuid:lead_id>/notes/",             LeadNoteListAPIView.as_view(),   name="lead-note-list"),

    # ==================================================
    # TWILIO APIs
    # (registered once only — no duplicates)
    # ==================================================
    path("twilio/send-sms/",  SendSMSAPIView.as_view(),          name="twilio-send-sms"),
    path("twilio/make-call/", MakeCallAPIView.as_view(),          name="twilio-make-call"),
    path("twilio/sms/",       TwilioMessageListAPIView.as_view(), name="twilio-sms-list"),
    path("twilio/calls/",     TwilioCallListAPIView.as_view(),    name="twilio-call-list"),

    # ==================================================
    # CAMPAIGN APIs
    # ==================================================
    path("campaigns/",                              CampaignCreateAPIView.as_view(),         name="campaign-create"),
    path("campaigns/<uuid:campaign_id>/update/",    CampaignUpdateAPIView.as_view(),         name="campaign-update"),
    path("campaigns/list/",                         CampaignListAPIView.as_view(),           name="campaign-list"),
    path("campaigns/<uuid:campaign_id>/",           CampaignGetAPIView.as_view(),            name="campaign-get"),
    path("campaigns/<uuid:campaign_id>/activate/",  CampaignActivateAPIView.as_view(),       name="campaign-activate"),
    path("campaigns/<uuid:campaign_id>/inactivate/",CampaignInactivateAPIView.as_view(),     name="campaign-inactivate"),
    path("campaigns/<uuid:campaign_id>/delete/",    CampaignSoftDeleteAPIView.as_view(),     name="campaign-soft-delete"),
    path("social-media-campaign/create/",           SocialMediaCampaignCreateAPIView.as_view(), name="social-media-campaign-create"),
    path("campaigns/email/create/",                 EmailCampaignCreateAPIView.as_view(),    name="email-campaign-create"),
    path("campaigns/zapier-callback/",              CampaignZapierCallbackAPIView.as_view(), name="campaign-zapier-callback"),
    path("mailchimp/webhook/",                      MailchimpWebhookAPIView.as_view(),       name="mailchimp-webhook"),
    path(
        "campaigns/<uuid:campaign_id>/facebook-insights/",
        CampaignFacebookInsightsAPIView.as_view(),
    ),

    # ==================================================
    # SALES PIPELINE APIs
    # ==================================================
    path("pipelines/create/",                               PipelineCreateAPIView.as_view(),       name="pipeline-create"),
    path("pipelines/",                                      PipelineListAPIView.as_view(),          name="pipeline-list"),
    path("pipelines/<uuid:pipeline_id>/",                   PipelineDetailAPIView.as_view(),        name="pipeline-detail"),
    path("pipelines/stages/create/",                        PipelineStageCreateAPIView.as_view(),   name="pipeline-stage-create"),
    path("pipelines/stages/<uuid:stage_id>/update/",        PipelineStageUpdateAPIView.as_view(),   name="pipeline-stage-update"),
    path("pipelines/stages/<uuid:stage_id>/rules/",         StageRuleSaveAPIView.as_view(),         name="pipeline-stage-rules-save"),
    path("pipelines/stages/<uuid:stage_id>/fields/",        StageFieldSaveAPIView.as_view(),        name="pipeline-stage-fields-save"),

    # ==================================================
    # TICKET APIs
    # ==================================================
    path("tickets/",                                TicketListAPIView.as_view(),            name="ticket-list"),
    path("tickets/create/",                         TicketCreateAPIView.as_view(),          name="ticket-create"),
    path("tickets/dashboard-count/",                TicketDashboardCountAPIView.as_view(),  name="ticket-dashboard-count"),
    path("tickets/<uuid:ticket_id>/",               TicketDetailAPIView.as_view(),          name="ticket-detail"),
    path("tickets/<uuid:ticket_id>/update/",        TicketUpdateAPIView.as_view(),          name="ticket-update"),
    path("tickets/<uuid:ticket_id>/assign/",        TicketAssignAPIView.as_view(),          name="ticket-assign"),
    path("tickets/<uuid:ticket_id>/status/",        TicketStatusUpdateAPIView.as_view(),    name="ticket-status-update"),
    path("tickets/<uuid:ticket_id>/documents/",     TicketDocumentUploadAPIView.as_view(),  name="ticket-document-upload"),
    path("tickets/<uuid:ticket_id>/delete/",        TicketDeleteAPIView.as_view(),          name="ticket-delete"),

    # ==================================================
    # LAB APIs
    # ==================================================
    path("labs/",                       LabListAPIView.as_view(),       name="lab-list"),
    path("labs/create/",                LabCreateAPIView.as_view(),     name="lab-create"),
    path("labs/<uuid:lab_id>/update/",  LabUpdateAPIView.as_view(),     name="lab-update"),
    path("labs/<uuid:lab_id>/delete/",  LabSoftDeleteAPIView.as_view(), name="lab-delete"),

    # ==================================================
    # TEMPLATE APIs
    # (document upload path must come BEFORE the generic detail path)
    # ==================================================
    path("templates/<str:template_type>/<uuid:template_id>/documents/", TemplateDocumentUploadAPIView.as_view(), name="template-document-upload"),
    path("templates/<str:template_type>/",                               TemplateListAPIView.as_view(),           name="template-list"),
    path("templates/<str:template_type>/create/",                        TemplateCreateAPIView.as_view(),         name="template-create"),
    path("templates/<str:template_type>/<uuid:template_id>/",            TemplateDetailAPIView.as_view(),         name="template-detail"),
    path("templates/<str:template_type>/<uuid:template_id>/update/",     TemplateUpdateAPIView.as_view(),         name="template-update"),
    path("templates/<str:template_type>/<uuid:template_id>/delete/",     TemplateDeleteAPIView.as_view(),         name="template-delete"),

    # ==================================================
    # IMAGE UPLOAD
    # ==================================================
    path("upload/image/", ImageUploadAPIView.as_view(), name="image-upload"),

    # ==================================================
    # MAIL INSIGHTS APIs
    #
    # How it works:
    #   Zapier "Appointment Booked" Zap → POST /api/mail-insights/
    #       body: { "appointments_booked": 1 }
    #   Zapier "Lead Created" Zap       → POST /api/mail-insights/
    #       body: { "leads_created": 1 }
    #   Django ADDS to existing cache (never overwrites)
    #   React Dashboard               → GET  /api/mail-insights/get/
    #   Reset counts for testing      → POST /api/mail-insights/reset/
    # ==================================================
    path("mail-insights/",        MailInsightsReceiveAPIView.as_view(), name="mail-insights-receive"),
    path("mail-insights/get/",    MailInsightsGetAPIView.as_view(),     name="mail-insights-get"),
    path("mail-insights/reset/",  MailInsightsResetAPIView.as_view(),   name="mail-insights-reset"),

    # ==================================================
    # INTERACTION COUNTS API
    # Powers the CommunicationChart in the React dashboard.
    # Returns: Email | SMS | Call | WhatsApp | Chatbot
    # ==================================================
    path("interactions/counts/", InteractionCountsAPIView.as_view(), name="interaction-counts"),

    # ==================================================
    # DEBUG — TEMPORARY
    # Open in browser: http://localhost:8000/api/debug/twilio-status/
    # Shows every status value stored in TwilioCall + TwilioMessage tables.
    # Remove this path once you've confirmed call statuses are correct.
    # ==================================================
    path("debug/twilio-status/",      TwilioDebugAPIView.as_view(),      name="twilio-debug"),
    path("debug/mail-insights-log/",  MailInsightsDebugAPIView.as_view(), name="mail-insights-debug"),

    # ==================================================
    # SOCIAL AUTH — LinkedIn
    # ==================================================
    path("linkedin/login/",     LinkedInLoginAPIView.as_view()),
    path("linkedin/callback/",  LinkedInCallbackAPIView.as_view()),
    path("linkedin/status/",    LinkedInStatusAPIView.as_view()),

    path("campaigns/<uuid:campaign_id>/mailchimp-insights/", CampaignMailchimpInsightsAPIView.as_view(), name="campaign-mailchimp-insights"),
    path("mailchimp/insights-callback/", MailchimpInsightsCallbackAPIView.as_view(), name="mailchimp-insights-callback"),

    # ==================================================
    # SOCIAL AUTH — Facebook
    # ==================================================
    path("facebook/login/",     FacebookLoginAPIView.as_view()),
    path("facebook/callback/",  FacebookCallbackAPIView.as_view()),
    path("facebook/status/",    FacebookStatusAPIView.as_view()),
    path("campaigns/<uuid:campaign_id>/facebook-debug/", FacebookDebugAPIView.as_view()),

    path("webhooks/gohighlevel/lead/", GoHighLevelLeadWebhookAPIView.as_view(), name="ghl-lead-webhook"),

    # Facebook Ads APIs
    # Facebook Ads APIs
    path("fb/campaigns/", FBCampaignListAPIView.as_view(), name="fb-campaigns"),
    path("fb/campaigns/create/", FBCampaignCreateAPIView.as_view(), name="fb-campaign-create"),
    path("fb/campaigns/<str:campaign_id>/insights/", FBCampaignInsightsAPIView.as_view(), name="fb-campaign-insights"),

]
        # ==================================================
# REPUTATION MANAGEMENT APIs
# ==================================================
path("reputation/requests/create/", ReviewRequestCreateAPIView.as_view(), name="reputation-request-create"),

path("reputation/requests/", ReviewRequestListAPIView.as_view(), name="reputation-request-list"),

path("reputation/requests/<uuid:request_id>/", ReviewRequestDetailAPIView.as_view(), name="reputation-request-detail"),

path("reputation/requests/<uuid:request_id>/reviews/", ReviewListAPIView.as_view(), name="reputation-reviews"),

path("reputation/dashboard/",ReputationDashboardAPIView.as_view(),name="reputation-dashboard"),

path("reputation/reviews/create/", ReviewCreateAPIView.as_view(), name="reputation-review-create"),
