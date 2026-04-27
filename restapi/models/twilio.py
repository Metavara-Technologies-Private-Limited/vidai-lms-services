from django.db import models
from restapi.models.clinic import Clinic
from restapi.models.lead import Lead   # adjust import if needed


# -------------------------------
# TWILIO MESSAGE MODEL
# -------------------------------
class TwilioMessage(models.Model):

    class DirectionChoices(models.TextChoices):
        INBOUND = "inbound", "Inbound"
        OUTBOUND = "outbound", "Outbound"

    class StatusChoices(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"
        RECEIVED = "received", "Received"

    lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="twilio_messages"
    )

    # ✅ ADD THIS (IMPORTANT)
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="twilio_messages",
        db_index=True
    )

    sid = models.CharField(max_length=255, unique=True)

    from_number = models.CharField(max_length=20)
    to_number = models.CharField(max_length=20)

    body = models.TextField()

    status = models.CharField(
        max_length=50,
        choices=StatusChoices.choices,
        null=True,
        blank=True
    )

    direction = models.CharField(
        max_length=20,
        choices=DirectionChoices.choices
    )

    raw_payload = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "twilio_messages"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["clinic"]),
            models.Index(fields=["sid"]),
        ]

    # ✅ AUTO ASSIGN CLINIC
    def save(self, *args, **kwargs):
        if self.lead and not self.clinic:
            self.clinic = getattr(self.lead, "clinic", None)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sid} - {self.direction}"
    

# -------------------------------
# TWILIO CALL MODEL
# -------------------------------
class TwilioCall(models.Model):

    class StatusChoices(models.TextChoices):
        INITIATED = "initiated", "Initiated"
        RINGING = "ringing", "Ringing"
        IN_PROGRESS = "in-progress", "In Progress"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        NO_ANSWER = "no-answer", "No Answer"
        BUSY = "busy", "Busy"

    lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="twilio_calls"
    )

    # ✅ ADD THIS
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="twilio_calls",
        db_index=True
    )

    sid = models.CharField(max_length=255, unique=True)

    from_number = models.CharField(max_length=20)
    to_number = models.CharField(max_length=20)

    status = models.CharField(
        max_length=50,
        choices=StatusChoices.choices,
        null=True,
        blank=True
    )

    raw_payload = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "twilio_calls"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["clinic"]),
            models.Index(fields=["sid"]),
        ]

    # ✅ AUTO ASSIGN CLINIC
    def save(self, *args, **kwargs):
        if self.lead and not self.clinic:
            self.clinic = getattr(self.lead, "clinic", None)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sid} - {self.status}"