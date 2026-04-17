from django.urls import path


from .views import *   



urlpatterns = [
    
    path("login/", LoginAPIView.as_view(), name="login"),
    path("auth/login/", LoginAPIView.as_view(), name="login-legacy"),
    path("token/refresh/", TokenRefreshAPIView.as_view(), name="token-refresh"),
    
    path('roles/create/', RoleCreateAPIView.as_view()),
    path('roles/list/', RoleListAPIView.as_view()),
    path('roles/<int:pk>/', RoleDetailAPIView.as_view()),
    path('roles/update/<int:pk>/', RoleUpdateAPIView.as_view()),
    path('roles/delete/<int:pk>/', RoleDeleteAPIView.as_view()),  
    
    path("permissions/<int:role_id>/", RolePermissionListAPIView.as_view()),
    path("permissions/create/", RolePermissionCreateAPIView.as_view()),
    path("permissions/<int:pk>/update/", RolePermissionUpdateAPIView.as_view()),

    path("users/permissions/", UserPermissionAPIView.as_view()),
    path("me/photo/", MyProfilePhotoAPIView.as_view(), name="my-profile-photo"),
    path("media/<path:path>", MediaFileAPIView.as_view(), name="media-file"),


    path("users/", UserCreateAPIView.as_view()),
    path("users/create/", UserCreateAPIView.as_view()),
    path("users/list/", UserListAPIView.as_view()),
    path("users/<int:pk>/", UserDetailAPIView.as_view()),
    path("users/<int:pk>/update/", UserUpdateAPIView.as_view()),
    path("users/<int:pk>/partial-update/", UserPartialUpdateAPIView.as_view()),
    path("users/<int:pk>/status/", UserStatusUpdateAPIView.as_view()),
    path("users/<int:pk>/delete/", UserDeleteAPIView.as_view()),
    
    # ============================
    # CLINIC
    # ============================
    path("clinics/", ClinicCreateAPIView.as_view(), name="clinic-create"),
    path("clinics/<int:clinic_id>/", ClinicUpdateAPIView.as_view(), name="clinic-update"),
    path("clinics/<int:clinic_id>/detail/", GetClinicView.as_view(), name="clinic-get"),
    path("clinics/search/", ClinicSearchAPIView.as_view(), name="clinic-search"),
   

    # ============================
    # EMPLOYEE / USER
    # ============================
    path("clinics/<int:clinic_id>/employees/", ClinicEmployeesAPIView.as_view(), name="clinic-employees"),
    path("employees/", EmployeeCreateAPIView.as_view(), name="employee-create"),
    path("employees/<int:employee_id>/update/", EmployeeUpdateAPIView.as_view(), name="employee-update"),

    # ============================
    # LEADS
    # ============================
    path("leads/", LeadCreateAPIView.as_view(), name="lead-create"),
    path("leads/<uuid:lead_id>/update/", LeadUpdateAPIView.as_view(), name="lead-update"),
    path("leads/list/", LeadListAPIView.as_view(), name="lead-list"),
    path("leads/<uuid:lead_id>/", LeadGetAPIView.as_view(), name="lead-get"),
    path("leads/<uuid:lead_id>/activate/", LeadActivateAPIView.as_view(), name="lead-activate"),
    path("leads/<uuid:lead_id>/inactivate/", LeadInactivateAPIView.as_view(), name="lead-inactivate"),
    path("leads/<uuid:lead_id>/delete/", LeadSoftDeleteAPIView.as_view(), name="lead-soft-delete"),
    path("lead-email/", LeadEmailAPIView.as_view(), name="lead-email"),
    path("lead-mail/", LeadMailListAPIView.as_view(), name="lead-mail-list"),

    # ============================
    # LEAD NOTES
    # ============================
    path("leads/notes/", LeadNoteCreateAPIView.as_view(), name="lead-note-create"),
    path("leads/notes/<uuid:note_id>/update/", LeadNoteUpdateAPIView.as_view(), name="lead-note-update"),
    path("leads/notes/<uuid:note_id>/delete/", LeadNoteDeleteAPIView.as_view(), name="lead-note-delete"),
    path("leads/<uuid:lead_id>/notes/", LeadNoteListAPIView.as_view(), name="lead-note-list"),

    # ============================
    # TWILIO
    # ============================
    path("twilio/send-sms/", SendSMSAPIView.as_view(), name="twilio-send-sms"),
    path("twilio/make-call/", MakeCallAPIView.as_view(), name="twilio-make-call"),
    path("twilio/sms-status-callback/", TwilioSMSStatusCallbackAPIView.as_view(), name="twilio-sms-status"),
    path("twilio/call-status-callback/", TwilioCallStatusCallbackAPIView.as_view(), name="twilio-call-status"),
    path("twilio/sms/", TwilioMessageListAPIView.as_view(), name="twilio-sms-list"),
    path("twilio/calls/", TwilioCallListAPIView.as_view(), name="twilio-call-list"),

    # ============================
    # CAMPAIGNS
    # ============================
    path("campaigns/", CampaignCreateAPIView.as_view(), name="campaign-create"),
    path("campaigns/<uuid:campaign_id>/update/", CampaignUpdateAPIView.as_view(), name="campaign-update"),
    path("campaigns/list/", CampaignListAPIView.as_view(), name="campaign-list"),
    path("campaigns/<uuid:campaign_id>/", CampaignGetAPIView.as_view(), name="campaign-get"),
    path("campaigns/<uuid:campaign_id>/activate/", CampaignActivateAPIView.as_view(), name="campaign-activate"),
    path("campaigns/<uuid:campaign_id>/inactivate/", CampaignInactivateAPIView.as_view(), name="campaign-inactivate"),
    path("campaigns/<uuid:campaign_id>/delete/", CampaignSoftDeleteAPIView.as_view(), name="campaign-delete"),

    path("social-media-campaign/create/", SocialMediaCampaignCreateAPIView.as_view(), name="social-campaign-create"),
    path("campaigns/email/create/", EmailCampaignCreateAPIView.as_view(), name="email-campaign-create"),

    path("campaigns/save-mailchimp-id/", EmailSaveMailchimpCampaignIdAPIView.as_view(), name="email-save-mailchimp-campaign-id"),

    path("campaigns/zapier-callback/", CampaignZapierCallbackAPIView.as_view(), name="zapier-callback"),
    path("mailchimp/webhook/", MailchimpWebhookAPIView.as_view(), name="mailchimp-webhook"),

    path("campaigns/<uuid:campaign_id>/facebook-insights/", CampaignFacebookInsightsAPIView.as_view(), name="facebook-insights"),
    path("campaigns/<uuid:campaign_id>/facebook-debug/", FacebookDebugAPIView.as_view(), name="facebook-debug"),

    path("campaigns/<uuid:campaign_id>/mailchimp-insights/", CampaignMailchimpInsightsAPIView.as_view(), name="mailchimp-insights"),
    path("mailchimp/insights-callback/", MailchimpInsightsCallbackAPIView.as_view(), name="mailchimp-callback"),

    # ============================
    # PIPELINE
    # ============================
    path("pipelines/create/", PipelineCreateAPIView.as_view(), name="pipeline-create"),
    path("pipelines/", PipelineListAPIView.as_view(), name="pipeline-list"),
    path("pipelines/<uuid:pipeline_id>/", PipelineDetailAPIView.as_view(), name="pipeline-detail"),
    path("pipelines/<uuid:pipeline_id>/duplicate/", PipelineDuplicateAPIView.as_view(), name="pipeline-duplicate"),
    path("pipelines/<uuid:pipeline_id>/archive/", PipelineArchiveAPIView.as_view(), name="pipeline-archive"),
    path("pipelines/<uuid:pipeline_id>/delete/", PipelineDeleteAPIView.as_view(), name="pipeline-delete"),
    path("pipelines/stages/create/", PipelineStageCreateAPIView.as_view(), name="stage-create"),
    path("pipelines/stages/<uuid:stage_id>/", StageDetailAPIView.as_view(), name="stage-detail"),
    path("pipelines/stages/<uuid:stage_id>/update/", PipelineStageUpdateAPIView.as_view(), name="stage-update"),
    path("pipelines/stages/<uuid:stage_id>/duplicate/", StageDuplicateAPIView.as_view(), name="stage-duplicate"),
    path("pipelines/stages/<uuid:stage_id>/archive/", StageArchiveAPIView.as_view(), name="stage-archive"),
    path("pipelines/stages/<uuid:stage_id>/delete/", StageDeleteAPIView.as_view(), name="stage-delete"),
    path("pipelines/stages/<uuid:stage_id>/rules/", StageRuleSaveAPIView.as_view(), name="stage-rules"),
    path("pipelines/stages/<uuid:stage_id>/fields/", StageFieldSaveAPIView.as_view(), name="stage-fields"),

    # ============================
    # TICKETS
    # ============================
    path("tickets/", TicketListAPIView.as_view(), name="ticket-list"),
    path("tickets/create/", TicketCreateAPIView.as_view(), name="ticket-create"),
    path("tickets/dashboard-count/", TicketDashboardCountAPIView.as_view(), name="ticket-dashboard"),
    path("tickets/<uuid:ticket_id>/", TicketDetailAPIView.as_view(), name="ticket-detail"),
    path("tickets/<uuid:ticket_id>/update/", TicketUpdateAPIView.as_view(), name="ticket-update"),
    path("tickets/<uuid:ticket_id>/assign/", TicketAssignAPIView.as_view(), name="ticket-assign"),
    path("tickets/<uuid:ticket_id>/status/", TicketStatusUpdateAPIView.as_view(), name="ticket-status"),
    path("tickets/<uuid:ticket_id>/documents/", TicketDocumentUploadAPIView.as_view(), name="ticket-doc"),
    path("tickets/<uuid:ticket_id>/delete/", TicketDeleteAPIView.as_view(), name="ticket-delete"),
    path("tickets/<uuid:ticket_id>/reply/", TicketReplyAPIView.as_view(), name="ticket-reply"),

    # ============================
    # LAB
    # ============================
    path("labs/", LabListAPIView.as_view(), name="lab-list"),
    path("labs/create/", LabCreateAPIView.as_view(), name="lab-create"),
    path("labs/<uuid:lab_id>/update/", LabUpdateAPIView.as_view(), name="lab-update"),
    path("labs/<uuid:lab_id>/delete/", LabSoftDeleteAPIView.as_view(), name="lab-delete"),

    # ============================
    # TEMPLATE
    # ============================
    path("templates/<str:template_type>/<uuid:template_id>/documents/", TemplateDocumentUploadAPIView.as_view(), name="template-doc"),
    path("templates/<str:template_type>/", TemplateListAPIView.as_view(), name="template-list"),
    path("templates/<str:template_type>/create/", TemplateCreateAPIView.as_view(), name="template-create"),
    path("templates/<str:template_type>/<uuid:template_id>/", TemplateDetailAPIView.as_view(), name="template-detail"),
    path("templates/<str:template_type>/<uuid:template_id>/update/", TemplateUpdateAPIView.as_view(), name="template-update"),
    path("templates/<str:template_type>/<uuid:template_id>/delete/", TemplateDeleteAPIView.as_view(), name="template-delete"),

    # ============================
    # IMAGE
    # ============================
    path("upload/image/", ImageUploadAPIView.as_view(), name="image-upload"),

    # ============================
    # MAIL INSIGHTS
    # ============================
    path("mail-insights/", MailInsightsReceiveAPIView.as_view(), name="mail-insights"),
    path("mail-insights/get/", MailInsightsGetAPIView.as_view(), name="mail-insights-get"),
    path("mail-insights/reset/", MailInsightsResetAPIView.as_view(), name="mail-insights-reset"),

    # ============================
    # INTERACTIONS
    # ============================
    path("interactions/counts/", InteractionCountsAPIView.as_view(), name="interaction-counts"),

    # ============================
    # DEBUG
    # ============================
    path("debug/twilio-status/", TwilioDebugAPIView.as_view(), name="debug-twilio"),
    path("debug/mail-insights-log/", MailInsightsDebugAPIView.as_view(), name="debug-mail"),

    # ============================
    # SOCIAL AUTH
    # ============================
    path("linkedin/login/", LinkedInLoginAPIView.as_view(), name="linkedin-login"),
    path("linkedin/callback/", LinkedInCallbackAPIView.as_view(), name="linkedin-callback"),
    path("linkedin/status/", LinkedInStatusAPIView.as_view(), name="linkedin-status"),

    path("facebook/login/", FacebookLoginAPIView.as_view(), name="facebook-login"),
    path("facebook/callback/", FacebookCallbackAPIView.as_view(), name="facebook-callback"),
    path("facebook/status/", FacebookStatusAPIView.as_view(), name="facebook-status"),

    path("google/login/", GoogleLoginAPIView.as_view()),
    path("google/callback/", GoogleCallbackAPIView.as_view()),

    path("clinics/<int:clinic_id>/social-accounts/", SocialAccountListAPIView.as_view(), name="social-account-list"),

    # ============================
    # WEBHOOK
    # ============================
    path("webhooks/gohighlevel/lead/", GoHighLevelLeadWebhookAPIView.as_view(), name="ghl-webhook"),

    # ============================
    # FACEBOOK ADS
    # ============================
    path("fb/campaigns/", FBCampaignListAPIView.as_view(), name="fb-campaigns"),
    path("fb/campaigns/create/", FBCampaignCreateAPIView.as_view(), name="fb-campaign-create"),
    path("fb/campaigns/<str:campaign_id>/insights/", FBCampaignInsightsAPIView.as_view(), name="fb-insights"),

    # ============================
    # REPUTATION
    # ============================
    path("reputation/requests/create/", ReviewRequestCreateAPIView.as_view(), name="review-create"),
    path("reputation/requests/", ReviewRequestListAPIView.as_view(), name="review-list"),
    path("reputation/requests/<uuid:request_id>/", ReviewRequestDetailAPIView.as_view(), name="review-detail"),
    path(
        "reputation/public/requests/<uuid:request_id>/",
        ReviewRequestPublicDetailAPIView.as_view(),
        name="review-public-detail",
    ),
    path("reputation/requests/<uuid:request_id>/reviews/", ReviewListAPIView.as_view(), name="review-sub-list"),
    path("reputation/dashboard/", ReputationDashboardAPIView.as_view(), name="reputation-dashboard"),
    path("reputation/reviews/create/", ReviewCreateAPIView.as_view(), name="review-submit"),


    path("sources/", ReferralSourceListAPIView.as_view(), name="referral-sources"),
    path("dashboard/", ReferralDashboardAPIView.as_view(), name="referral-dashboard"),
    
    path("reports/calls/", CallReportView.as_view(), name="call-reports"),
    path("reports/campaigns/", CampaignReportView.as_view(), name="campaign-reports"),

    # ============================
    # PROXY
    # ============================
    path("proxy/login/", LoginProxyAPIView.as_view(), name="login-proxy"),
    path("me/profile/", ProfileProxyAPIView.as_view(), name="profile"),
    path("users-search/", UsersProxyAPIView.as_view(), name="users"),
]
