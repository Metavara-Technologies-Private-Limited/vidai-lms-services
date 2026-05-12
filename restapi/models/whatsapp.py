# ─────────────────────────────────────────────────────────────────────────────
# restapi/models/whatsapp.py
#
# NOTE: WhatsAppTemplate is NOT created here because you already have
#       TemplateWhatsApp (restapi_template_whatsapp table) in your DB.
#       WhatsAppMessage references TemplateWhatsApp via FK.
# ─────────────────────────────────────────────────────────────────────────────

from django.db import models
from restapi.models.clinic            import Clinic
from restapi.models.lead              import Lead
from restapi.models.template_whatsapp import TemplateWhatsApp   # ✅ FIXED


class WhatsAppMessage(models.Model):

    class StatusChoices(models.TextChoices):
        QUEUED      = "queued",       "Queued"
        SENT        = "sent",         "Sent"
        DELIVERED   = "delivered",    "Delivered"
        READ        = "read",         "Read"
        FAILED      = "failed",       "Failed"
        UNDELIVERED = "undelivered",  "Undelivered"

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
        TemplateWhatsApp,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_messages",
    )

    sid             = models.CharField(max_length=255, unique=True)
    from_number     = models.CharField(max_length=30)
    to_number       = models.CharField(max_length=30)
    template_name   = models.CharField(max_length=255)
    language        = models.CharField(max_length=20, default="en")
    variable_values = models.JSONField(default=list)

    status = models.CharField(
        max_length=50,
        choices=StatusChoices.choices,
        default=StatusChoices.QUEUED,
        db_index=True,
    )

    raw_payload = models.JSONField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "whatsapp_messages"
        ordering = ["-created_at"]
        indexes  = [
            models.Index(fields=["clinic"]),
            models.Index(fields=["sid"]),
            models.Index(fields=["status"]),
            models.Index(fields=["to_number"]),
        ]

    def save(self, *args, **kwargs):
        if self.lead and not self.clinic:
            self.clinic = getattr(self.lead, "clinic", None)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sid} → {self.to_number} [{self.status}]"