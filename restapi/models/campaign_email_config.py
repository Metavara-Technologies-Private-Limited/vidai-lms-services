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
