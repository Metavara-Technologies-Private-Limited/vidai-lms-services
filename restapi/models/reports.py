from django.db import models
from django.contrib.auth.models import User

from restapi.models.lead import Lead
from restapi.models.campaign import Campaign


# =========================
# CALL LOGS
# =========================
class CallLog(models.Model):

    CALL_TYPE_CHOICES = (
        ("incoming", "Incoming"),
        ("outgoing", "Outgoing"),
    )

    STATUS_CHOICES = (
        ("connected", "Connected"),
        ("not_connected", "Not Connected"),
    )

    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="call_logs"
    )

    phone_number = models.CharField(max_length=20)

    call_type = models.CharField(
        max_length=10,
        choices=CALL_TYPE_CHOICES
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES
    )

    duration = models.IntegerField(help_text="Duration in seconds")

    received_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    transcript = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "restapi_call_log"
        ordering = ["-created_at"]


# =========================
# CAMPAIGN METRICS (IMPORTANT)
# =========================
class CampaignMetrics(models.Model):

    campaign = models.ForeignKey(
        Campaign,  # ✅ USING YOUR EXISTING MODEL
        on_delete=models.CASCADE,
        related_name="metrics"
    )

    # 🔥 VERY IMPORTANT FIELD
    date = models.DateField()

    # Ads metrics
    impressions = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    conversions = models.IntegerField(default=0)
    spend = models.FloatField(default=0.0)

    # Email metrics
    sent = models.IntegerField(default=0)
    opened = models.IntegerField(default=0)
    unsubscribed = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "restapi_campaign_metrics"
        unique_together = ("campaign", "date")