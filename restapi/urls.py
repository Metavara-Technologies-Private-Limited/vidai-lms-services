from django.urls import path

from .views import (

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
    
    
)

urlpatterns = [


# ==================================================
# Lead APIs
# ==================================================

    # Create Lead (POST)
    path(
        "leads/",
        LeadCreateAPIView.as_view(),
        name="lead-create"
    ),

    # ✅ Update Lead (PUT)
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

    


]
