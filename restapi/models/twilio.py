from django.db import models
from restapi.models.lead import Lead   # adjust import if needed


# -------------------------------
# TWILIO MESSAGE MODEL
# -------------------------------
class TwilioMessage(models.Model):

    DIRECTION_CHOICES = (
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
    )

    lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="twilio_messages"
    )

    sid = models.CharField(max_length=255, unique=True)
    from_number = models.CharField(max_length=20)
    to_number = models.CharField(max_length=20)
    body = models.TextField()
    status = models.CharField(max_length=50, null=True, blank=True)
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)

    raw_payload = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "twilio_messages"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.sid} - {self.direction}"
    

# -------------------------------
# TWILIO CALL MODEL
# -------------------------------
class TwilioCall(models.Model):

    lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="twilio_calls"
    )

    sid = models.CharField(max_length=255, unique=True)
    from_number = models.CharField(max_length=20)
    to_number = models.CharField(max_length=20)
    status = models.CharField(max_length=50, null=True, blank=True)

    raw_payload = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "twilio_calls"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.sid} - {self.status}"