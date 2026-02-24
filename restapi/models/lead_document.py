import uuid
from django.db import models
from .lead import Lead


class LeadDocument(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="documents"
    )

    file = models.FileField(
        upload_to="lead_documents/"
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        db_table = "restapi_lead_document"

    def __str__(self):
        return f"{self.lead.full_name} - Document"