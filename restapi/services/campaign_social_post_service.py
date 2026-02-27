from django.shortcuts import get_object_or_404
from django.utils import timezone

from restapi.models import Campaign, CampaignSocialPost


def create_pending_social_post(campaign, platform):
    """
    Called when LMS sends campaign to Zapier.
    Creates a pending record.
    """
    return CampaignSocialPost.objects.create(
        campaign=campaign,
        platform_name=platform,
        status=CampaignSocialPost.PENDING
    )


def handle_zapier_callback(validated_data):
    """
    Updates CampaignSocialPost based on Zapier response.
    """

    campaign = get_object_or_404(
        Campaign,
        id=validated_data["campaign_id"]
    )

    social_post = CampaignSocialPost.objects.filter(
        campaign=campaign,
        platform_name=validated_data["platform"]
    ).order_by("-created_at").first()

    if not social_post:
        # fallback: create one if not found
        social_post = CampaignSocialPost.objects.create(
            campaign=campaign,
            platform_name=validated_data["platform"]
        )

    if validated_data["status"] == CampaignSocialPost.POSTED:
        social_post.mark_posted(
            post_id=validated_data.get("post_id")
        )
    else:
        social_post.mark_failed(
            error_message=validated_data.get("error_message")
        )

    return social_post
