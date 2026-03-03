from django.db import models

from .campaign import Campaign


class CampaignSocialMediaConfig(models.Model):

    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"

    PLATFORM_CHOICES = (
        (INSTAGRAM, "Instagram"),
        (FACEBOOK, "Facebook"),
        (LINKEDIN, "LinkedIn"),
    )

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="social_configs"
    )

    # ✅ POST ID (Correct Place)
    post_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Stores social media post ID"
    )

    platform_name = models.CharField(
        max_length=50,
        choices=PLATFORM_CHOICES
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)