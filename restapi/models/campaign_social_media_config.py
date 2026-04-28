# from django.db import models

# from .campaign import Campaign


# class CampaignSocialMediaConfig(models.Model):

#     INSTAGRAM  = "instagram"
#     FACEBOOK   = "facebook"
#     LINKEDIN   = "linkedin"
#     GOOGLE_ADS = "google_ads"  # ✅ ADDED

#     PLATFORM_CHOICES = (
#         (INSTAGRAM,  "Instagram"),
#         (FACEBOOK,   "Facebook"),
#         (LINKEDIN,   "LinkedIn"),
#         (GOOGLE_ADS, "Google Ads"),  # ✅ ADDED
#     )

#     campaign = models.ForeignKey(
#         Campaign,
#         on_delete=models.CASCADE,
#         related_name="social_configs"
#     )

#     # ✅ POST ID (Correct Place)
#     post_id = models.CharField(
#         max_length=255,
#         null=True,
#         blank=True,
#         help_text="Stores social media post ID"
#     )

#     platform_name = models.CharField(
#         max_length=50,
#         choices=PLATFORM_CHOICES
#     )

#     is_active = models.BooleanField(default=True)

#     created_at = models.DateTimeField(auto_now_add=True)

#     # ✅ INSIGHTS
#     insights = models.JSONField(
#         null=True,
#         blank=True,
#         help_text="Stores campaign insights fetched from social media platforms"
#     )



from django.db import models

from .campaign import Campaign

class CampaignSocialMediaConfig(models.Model):
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    GOOGLE_ADS = "google_ads"

    PLATFORM_CHOICES = (
        (INSTAGRAM, "Instagram"),
        (FACEBOOK, "Facebook"),
        (LINKEDIN, "LinkedIn"),
        (GOOGLE_ADS, "Google Ads"),
    )

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="social_configs"
    )

    post_id = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    platform_name = models.CharField(
        max_length=50,
        choices=PLATFORM_CHOICES
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    insights = models.JSONField(
        null=True,
        blank=True
    )

    class Meta:
        unique_together = ("campaign", "platform_name")