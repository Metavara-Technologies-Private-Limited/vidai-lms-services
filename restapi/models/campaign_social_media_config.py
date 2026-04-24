# # restapi\models\campaign_social_media_config.py
# from django.db import models

# from .campaign import Campaign


# class CampaignSocialMediaConfig(models.Model):

#     INSTAGRAM = "instagram"
#     FACEBOOK = "facebook"
#     LINKEDIN = "linkedin"

#     PLATFORM_CHOICES = (
#         (INSTAGRAM, "Instagram"),
#         (FACEBOOK, "Facebook"),
#         (LINKEDIN, "LinkedIn"),
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

    platform_name = models.CharField(
        max_length=50,
        choices=PLATFORM_CHOICES
    )

    # ✅ Use generic names so they work for all platforms
    access_token = models.TextField(
        null=True, 
        blank=True, 
        help_text="OAuth2 token for API calls (LinkedIn, FB, etc.)"
    )
    
    # Store the specific ID for the platform (Page ID for FB, Ad Account for LI)
    platform_account_id = models.CharField(
        max_length=255, 
        null=True, 
        blank=True,
        help_text="Platform specific ID (e.g., LinkedIn Ad Account ID or FB Page ID)"
    )


    post_id = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('campaign', 'platform_name')

    def __str__(self):
        return f"{self.campaign.campaign_name} - {self.platform_name}"