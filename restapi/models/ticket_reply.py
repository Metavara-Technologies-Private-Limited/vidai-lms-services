import uuid
from django.db import models

from .ticket import Ticket
from .employee import Employee


class TicketReply(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="replies"
    )

    subject = models.CharField(max_length=255)
    message = models.TextField()

    to_emails = models.JSONField(default=list)
    cc_emails = models.JSONField(default=list, blank=True)
    bcc_emails = models.JSONField(default=list, blank=True)

    sent_by = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ticket_replies"
    )

    STATUS_CHOICES = [
        ("sent", "Sent"),
        ("failed", "Failed"),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="sent")
    failed_reason = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reply to {self.ticket.ticket_no} at {self.created_at}"
