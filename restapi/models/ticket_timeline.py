import uuid
from django.db import models

from .ticket import Ticket
from .employee import Employee

class TicketTimeline(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ticket = models.ForeignKey(
        "Ticket",
        on_delete=models.CASCADE,
        related_name="timeline"
    )

    action = models.CharField(max_length=255)
    remark = models.TextField(null=True, blank=True)

    done_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        related_name="ticket_actions"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ticket.ticket_no} - {self.action}"
