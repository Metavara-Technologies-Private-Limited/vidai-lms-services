from django.db import transaction
from django.utils import timezone
from restapi.models import (
    Campaign,
    CampaignSocialMediaConfig,
    CampaignEmailConfig,
)


# =====================================================
# AUTO STATUS (ONLY FOR DRAFT)
# =====================================================
def apply_auto_status(campaign):
    """
    Only auto-manage when status is DRAFT.
    If user sends scheduled/live/paused/etc,
    we respect it and do NOT override.
    """
    now = timezone.now()

    if campaign.status == Campaign.Status.DRAFT:

        if campaign.selected_start > now:
            campaign.status = Campaign.Status.SCHEDULED

        elif campaign.selected_start <= now <= campaign.selected_end:
            campaign.status = Campaign.Status.LIVE

        elif now > campaign.selected_end:
            campaign.status = Campaign.Status.COMPLETED

        campaign.save()


# =====================================================
# CREATE
# =====================================================
@transaction.atomic
def create_campaign(validated_data):
    social_media_data = validated_data.pop("social_media", [])
    email_data = validated_data.pop("email", [])

    campaign = Campaign.objects.create(**validated_data)

    # ✅ Apply auto status only for draft
    apply_auto_status(campaign)

    # -----------------------------
    # Social Media Config
    # -----------------------------
    for sm in social_media_data:
        CampaignSocialMediaConfig.objects.create(
            campaign=campaign,
            platform_name=sm["platform_name"],
            is_active=sm.get("is_active", True),
        )

    # -----------------------------
    # Email Config
    # -----------------------------
    for email in email_data:
        CampaignEmailConfig.objects.create(
            campaign=campaign,
            audience_name=email["audience_name"],
            subject=email["subject"],
            email_body=email["email_body"],
            template_name=email.get("template_name"),
            sender_email=email.get("sender_email"),
            scheduled_at=email.get("scheduled_at"),
            is_active=email.get("is_active", True),
        )

    return campaign


# =====================================================
# UPDATE
# =====================================================
@transaction.atomic
def update_campaign(instance, validated_data):
    social_media_data = validated_data.pop("social_media", [])
    email_data = validated_data.pop("email", [])

    # Update campaign fields
    for field, value in validated_data.items():
        setattr(instance, field, value)

    instance.save()

    # ✅ Apply auto status only if still draft
    apply_auto_status(instance)

    return instance
