from django.db import transaction
from restapi.models import (
    Campaign,
    CampaignSocialMediaConfig,
    CampaignEmailConfig,
)
from rest_framework.exceptions import ValidationError 

# =====================================================
# CREATE
# =====================================================
@transaction.atomic
def create_campaign(validated_data):
    social_media_data = validated_data.pop("social_media", [])
    email_data = validated_data.pop("email", [])

    campaign = Campaign.objects.create(**validated_data)

    for sm in social_media_data:
        CampaignSocialMediaConfig.objects.create(
            campaign=campaign,
            platform_name=sm["platform_name"],
            is_active=sm.get("is_active", True),
        )

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

    # -----------------------------
    # Update campaign fields
    # -----------------------------
    for field, value in validated_data.items():
        setattr(instance, field, value)

    instance.save()

    # -----------------------------
    # SOCIAL MEDIA (ID SAFE)
    # -----------------------------
    existing_sm = {
        sm.id: sm for sm in instance.social_configs.all()
    }

    for sm in social_media_data:
        sm_id = sm.get("id")

        if not sm_id:
            raise ValidationError("Social media id is required")

        if sm_id not in existing_sm:
            raise ValidationError(
                f"Social media id {sm_id} does not belong to this campaign"
            )

        obj = existing_sm[sm_id]
        obj.platform_name = sm["platform_name"]
        obj.is_active = sm.get("is_active", True)
        obj.save()

    # -----------------------------
    # EMAIL (ID SAFE)
    # -----------------------------
    existing_email = {
        e.id: e for e in instance.email_configs.all()
    }

    for email in email_data:
        email_id = email.get("id")

        if not email_id:
            raise ValidationError("Email id is required")

        if email_id not in existing_email:
            raise ValidationError(
                f"Email id {email_id} does not belong to this campaign"
            )

        obj = existing_email[email_id]
        obj.audience_name = email["audience_name"]
        obj.subject = email["subject"]
        obj.email_body = email["email_body"]
        obj.template_name = email.get("template_name")
        obj.sender_email = email.get("sender_email")
        obj.scheduled_at = email.get("scheduled_at")
        obj.is_active = email.get("is_active", True)
        obj.save()

    instance.refresh_from_db()
    return instance
