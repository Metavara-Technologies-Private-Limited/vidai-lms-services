from django.db import models
from .campaign import Campaign

class CampaignSocialMediaConfig(models.Model):

    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    GOOGLE_ADS = "google_ads"   # ✅ FIX ADDED

    PLATFORM_CHOICES = (
        (INSTAGRAM,  "Instagram"),
        (FACEBOOK,   "Facebook"),
        (LINKEDIN,   "LinkedIn"),
        (GOOGLE_ADS, "Google Ads"),  # ✅ now works
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

    access_token = models.TextField(
        null=True, 
        blank=True, 
        help_text="OAuth2 token for API calls (LinkedIn, FB, etc.)"
    )
    
    platform_account_id = models.CharField(
        max_length=255, 
        null=True, 
        blank=True,
        help_text="Platform specific ID (e.g., LinkedIn Ad Account ID or FB Page ID)"
    )

    post_id = models.CharField(max_length=255, null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)