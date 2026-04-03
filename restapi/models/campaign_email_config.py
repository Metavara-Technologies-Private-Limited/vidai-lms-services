from django.db import models
from django.utils import timezone

from .campaign import Campaign


class CampaignEmailConfig(models.Model):
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="email_configs"
    )

    # 🔹 Audience
    audience_name = models.CharField(
        max_length=255,
        help_text="Audience list name or identifier"
    )

    # 🔹 Email content
    subject = models.CharField(max_length=255)
    email_body = models.TextField()

    # 🔹 Optional template support
    template_name = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    # 🔹 Sender (optional for now)
    sender_email = models.EmailField(
        null=True,
        blank=True
    )

    # 🔹 Scheduling (used in step 3 UI)
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True
    )

    # 🔹 Mailchimp Campaign ID ✅ (ONLY ADDED FIELD)
    mailchimp_campaign_id = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    # =====================================================
    # ✅ Mailchimp Insights — Single JSON Column
    # =====================================================
    insights = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "Cached Mailchimp campaign insights stored as a single JSON dict. "
            "Keys: emails_sent, opens, open_rate, clicks, click_rate, "
            "bounces, unsubscribes, last_open, last_click, synced_at. "
            "Saved when GET /api/campaigns/<id>/mailchimp-insights/ is called. "
            "Read by CampaignListAPIView and CampaignGetAPIView as a fallback "
            "so the dashboard always shows the last known data."
        )
    )

    def __str__(self):
        return f"{self.campaign.campaign_name} - {self.audience_name}"