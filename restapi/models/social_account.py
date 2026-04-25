from django.db import models
from .clinic import Clinic


class SocialAccount(models.Model):
    PLATFORM_CHOICES = (
        ("facebook", "Facebook"),
        ("instagram", "Instagram"),
        ("linkedin", "LinkedIn"),
        ("google", "Google"),
    )

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)

    # Facebook data
    access_token = models.TextField()
    refresh_token = models.TextField(null=True, blank=True)   # ✅ ADD
    expires_at = models.DateTimeField(null=True, blank=True)  # ✅ ADD
    page_id = models.CharField(max_length=100, null=True, blank=True)
    page_name = models.CharField(max_length=255, null=True, blank=True)
    user_token = models.TextField(blank=True, null=True)

    # Google Ads
    customer_id = models.CharField(max_length=50, null=True, blank=True)  # ← added

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    
    
    account_id = models.CharField(max_length=100, null=True, blank=True)
    org_urn = models.CharField(max_length=255, null=True, blank=True)
    campaign_group = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        unique_together = ("clinic", "platform")

    def __str__(self):
        return f"{self.clinic} - {self.platform}"