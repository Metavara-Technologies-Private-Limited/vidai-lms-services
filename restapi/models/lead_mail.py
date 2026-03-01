from django.db import models
from django.utils import timezone
from .lead import Lead


class LeadEmail(models.Model):

    class StatusChoices(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SCHEDULED = "SCHEDULED", "Scheduled"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    # 🔹 Lead Reference
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="emails"
    )

    # 🔹 Email Content
    subject = models.CharField(max_length=255)
    email_body = models.TextField()

    # 🔹 Sender (Optional)
    sender_email = models.EmailField(
        null=True,
        blank=True
    )

    # 🔹 Scheduling
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True
    )

    # 🔹 Status Tracking
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.DRAFT
    )

    # 🔹 Tracking Fields
    sent_at = models.DateTimeField(null=True, blank=True)
    failed_reason = models.TextField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.lead.id} - {self.subject} - {self.status}"