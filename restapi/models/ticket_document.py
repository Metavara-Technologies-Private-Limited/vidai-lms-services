import uuid
from django.db import models
from .ticket import Ticket


class Document(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="documents"
    )

    file = models.FileField(upload_to="ticket_documents/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Document - {self.ticket.ticket_no}"
