# ─────────────────────────────────────────────────────────────────────────────
# ADD THESE TWO MODELS to your existing models file (e.g. restapi/models/twilio.py)
# DO NOT remove TwilioMessage or TwilioCall — append below them
# ─────────────────────────────────────────────────────────────────────────────

from django.db import models
from restapi.models.clinic import Clinic
from restapi.models.lead import Lead


# ─────────────────────────────────────────────────────────────────────────────
# WHATSAPP TEMPLATE MODEL
# Stores Meta-approved templates created from your UI
# ─────────────────────────────────────────────────────────────────────────────

class WhatsAppTemplate(models.Model):

    class StatusChoices(models.TextChoices):
        PENDING   = "PENDING",   "Pending"
        APPROVED  = "APPROVED",  "Approved"
        REJECTED  = "REJECTED",  "Rejected"
        PAUSED    = "PAUSED",    "Paused"
        DISABLED  = "DISABLED",  "Disabled"

    class CategoryChoices(models.TextChoices):
        MARKETING      = "MARKETING",      "Marketing"
        UTILITY        = "UTILITY",        "Utility"
        AUTHENTICATION = "AUTHENTICATION", "Authentication"

    # Meta identifiers
    meta_template_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        help_text="Template ID returned by Meta Graph API",
    )
    name = models.CharField(
        max_length=255,
        help_text="Template name (lowercase, underscores only)",
    )
    category = models.CharField(
        max_length=50,
        choices=CategoryChoices.choices,
        default=CategoryChoices.UTILITY,
    )
    language = models.CharField(
        max_length=20,
        default="en",
        help_text="BCP-47 language code e.g. en, en_US, hi",
    )

    # Content
    header_text = models.CharField(max_length=60, blank=True, default="")
    body_text   = models.TextField(
        help_text="Message body with {{1}}, {{2}} placeholders",
    )
    footer_text = models.CharField(max_length=60, blank=True, default="")

    # Variables — list of example values e.g. ["John", "10 AM"]
    variables = models.JSONField(default=list, blank=True)

    # Approval status synced from Meta
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
        db_index=True,
    )

    # Full Meta API response stored for debugging
    raw_payload = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "whatsapp_templates"
        ordering = ["-created_at"]
        indexes  = [
            models.Index(fields=["status"]),
            models.Index(fields=["name", "language"]),
        ]

    def __str__(self):
        return f"{self.name} [{self.language}] — {self.status}"


# ─────────────────────────────────────────────────────────────────────────────
# WHATSAPP MESSAGE MODEL
# Stores every outbound WhatsApp message sent via Twilio
# ─────────────────────────────────────────────────────────────────────────────

class WhatsAppMessage(models.Model):

    class StatusChoices(models.TextChoices):
        QUEUED     = "queued",     "Queued"
        SENT       = "sent",       "Sent"
        DELIVERED  = "delivered",  "Delivered"
        READ       = "read",       "Read"
        FAILED     = "failed",     "Failed"
        UNDELIVERED = "undelivered", "Undelivered"

    lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_messages",
    )
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_messages",
        db_index=True,
    )
    template = models.ForeignKey(
        WhatsAppTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
    )

    # Twilio message SID
    sid           = models.CharField(max_length=255, unique=True)
    from_number   = models.CharField(max_length=30)
    to_number     = models.CharField(max_length=30)

    # Template info at time of sending (kept even if template changes later)
    template_name   = models.CharField(max_length=255)
    language        = models.CharField(max_length=20, default="en")
    variable_values = models.JSONField(default=list)   # ["John", "10 AM", ...]

    status = models.CharField(
        max_length=50,
        choices=StatusChoices.choices,
        default=StatusChoices.QUEUED,
        db_index=True,
    )

    # Full Twilio + Meta response for debugging
    raw_payload = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "whatsapp_messages"
        ordering = ["-created_at"]
        indexes  = [
            models.Index(fields=["clinic"]),
            models.Index(fields=["sid"]),
            models.Index(fields=["status"]),
            models.Index(fields=["to_number"]),
        ]

    # Auto-assign clinic from lead if not set
    def save(self, *args, **kwargs):
        if self.lead and not self.clinic:
            self.clinic = getattr(self.lead, "clinic", None)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sid} → {self.to_number} [{self.status}]"