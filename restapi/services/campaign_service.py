from django.db import transaction
from django.utils import timezone

from restapi.models import (
    Campaign,
    CampaignSocialMediaConfig,
    CampaignEmailConfig,
)
from restapi.models.social_account import SocialAccount
from restapi.views import post_to_facebook  # adjust if needed


# =====================================================
# AUTO STATUS
# =====================================================
def apply_auto_status(campaign):
    now = timezone.now()

    if campaign.status == Campaign.Status.DRAFT:

        if campaign.selected_start > now:
            campaign.status = Campaign.Status.SCHEDULED

        elif campaign.selected_start <= now <= campaign.selected_end:
            campaign.status = Campaign.Status.LIVE

        elif now > campaign.selected_end:
            campaign.status = Campaign.Status.COMPLETED

        campaign.save(update_fields=["status"])


# =====================================================
# CREATE CAMPAIGN
# =====================================================
@transaction.atomic
def create_campaign(validated_data):

    social_media_data = validated_data.pop("social_media", [])
    email_data = validated_data.pop("email", [])

    # -----------------------------
    # Create Campaign
    # -----------------------------
    campaign = Campaign.objects.create(**validated_data)

    apply_auto_status(campaign)

    # =====================================================
    # SOCIAL MEDIA CONFIG + AUTO POST
    # =====================================================
    for sm in social_media_data:

        config = CampaignSocialMediaConfig.objects.create(
            campaign=campaign,
            platform_name=sm["platform_name"],
            is_active=sm.get("is_active", True),
        )

        platform = sm["platform_name"].lower()

        # ---------------------------------------------
        # FACEBOOK
        # ---------------------------------------------
        if platform == "facebook" and config.is_active:

            social_account = SocialAccount.objects.filter(
                clinic=campaign.clinic,
                platform="facebook",
                is_active=True
            ).first()

            if social_account:

                print("Posting to Facebook...")

                fb_response = post_to_facebook(
                    page_id=social_account.page_id,
                    page_token=social_account.access_token,
                    message=campaign.campaign_content
                )

                print("FACEBOOK RESPONSE:", fb_response)

                post_id = fb_response.get("id")

                if post_id:

                    # 🔥 USE UPDATE INSTEAD OF SAVE
                    CampaignSocialMediaConfig.objects.filter(
                        id=config.id
                    ).update(post_id=post_id)

                    # 🔥 REFRESH FROM DB
                    config.refresh_from_db()

                    print("POST ID SAVED IN DB:", config.post_id)

                else:
                    print("Facebook did not return post_id")

            else:
                print("No active Facebook account found")

    # =====================================================
    # EMAIL CONFIG
    # =====================================================
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

    # 🔥 FINAL DB VERIFICATION
    print("FINAL DB STATE:",
        list(
            CampaignSocialMediaConfig.objects
            .filter(campaign=campaign)
            .values("platform_name", "post_id")
        )
    )

    return campaign


# =====================================================
# UPDATE CAMPAIGN
# =====================================================
@transaction.atomic
def update_campaign(instance, validated_data):

    social_media_data = validated_data.pop("social_media", [])
    email_data = validated_data.pop("email", [])

    for field, value in validated_data.items():
        setattr(instance, field, value)

    instance.save()

    apply_auto_status(instance)

    # ⚠️ WARNING:
    # This deletes old post_ids
    if social_media_data:
        instance.social_configs.all().delete()

        for sm in social_media_data:
            CampaignSocialMediaConfig.objects.create(
                campaign=instance,
                platform_name=sm["platform_name"],
                is_active=sm.get("is_active", True),
            )

    if email_data:
        instance.email_configs.all().delete()

        for email in email_data:
            CampaignEmailConfig.objects.create(
                campaign=instance,
                audience_name=email["audience_name"],
                subject=email["subject"],
                email_body=email["email_body"],
                template_name=email.get("template_name"),
                sender_email=email.get("sender_email"),
                scheduled_at=email.get("scheduled_at"),
                is_active=email.get("is_active", True),
            )

    return instance