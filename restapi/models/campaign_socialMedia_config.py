from django.db import models

from .campaign import Campaign


class CampaignSocialMediaConfig(models.Model):
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="social_configs"
    )

    platform_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
