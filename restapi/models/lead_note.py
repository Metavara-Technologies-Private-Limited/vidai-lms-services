import uuid
from django.db import models

from .lead import Lead
from .employee import Employee


class LeadNote(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # --------------------------------------------------
    # Relationships
    # --------------------------------------------------

    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="notes"
    )

    created_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        related_name="lead_notes"
    )

    # --------------------------------------------------
    # Core Fields
    # --------------------------------------------------

    title = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Short title for the note."
    )

    note = models.TextField(
        help_text="Note content added for the lead."
    )

    # --------------------------------------------------
    # Status Flags
    # --------------------------------------------------

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    # --------------------------------------------------
    # Audit Fields
    # --------------------------------------------------

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "restapi_lead_note"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - Lead {self.lead_id}"