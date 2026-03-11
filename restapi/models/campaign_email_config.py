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

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    # =====================================================
    # ✅ Mailchimp Insights — Single JSON Column
    # =====================================================
    # All Mailchimp insight data is stored here as one JSON dict.
    # Replaces the 10 individual columns (emails_sent, opens, open_rate,
    # clicks, click_rate, bounces, unsubscribes, last_open, last_click,
    # insights_synced_at) that were added in the previous session.
    #
    # Why a single JSON column?
    #   - Cleaner DB schema: one column instead of ten
    #   - Flexible: add new Mailchimp keys in the future without new migrations
    #   - Dashboard fallback: CampaignListAPIView and CampaignGetAPIView
    #     read from insights dict (email_config.insights.get("opens") etc.)
    #
    # Saved when GET /api/campaigns/<id>/mailchimp-insights/ is called.
    # Used by dashboard fallback in CampaignListAPIView and CampaignGetAPIView
    # so the UI NEVER shows 0 even if Mailchimp API is temporarily down.
    #
    # Example value stored in DB:
    # {
    #     "emails_sent":   6,
    #     "opens":         3,
    #     "open_rate":     50.0,
    #     "clicks":        1,
    #     "click_rate":    16.7,
    #     "bounces":       0,
    #     "unsubscribes":  0,
    #     "last_open":     "2026-03-10T11:54:00+00:00",
    #     "last_click":    null,
    #     "synced_at":     "2026-03-11T10:54:32+00:00"
    # }
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