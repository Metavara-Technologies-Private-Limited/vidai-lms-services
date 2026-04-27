from django.db import models
from django.utils import timezone

from .lead import Lead
from .clinic import Clinic


class LeadEmail(models.Model):

    class StatusChoices(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SCHEDULED = "SCHEDULED", "Scheduled"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    # 🔹 Relations
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="emails"
    )

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead_emails",
        db_index=True
    )

    # 🔹 Email Content
    subject = models.CharField(max_length=255)
    email_body = models.TextField()

    sender_email = models.EmailField(null=True, blank=True)

    # 🔹 Scheduling
    scheduled_at = models.DateTimeField(null=True, blank=True)

    # 🔹 Status
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.DRAFT
    )

    # 🔹 Tracking
    sent_at = models.DateTimeField(null=True, blank=True)
    failed_reason = models.TextField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    # ✅ AUTO ASSIGN CLINIC
    def save(self, *args, **kwargs):
        if self.lead and not self.clinic:
            self.clinic = getattr(self.lead, "clinic", None)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.lead.id} - {self.subject} - {self.status}"