import uuid
from django.db import models

from .lead import Lead
from .employee import Employee


class LeadNote(models.Model):
    """
    LeadNote Model

    Purpose:
    Stores internal notes added to a Lead.

    One Lead can have multiple notes.
    Each note is created by an employee.
    """

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

    # --------------------------------------------------
    # Meta Configuration
    # --------------------------------------------------

    class Meta:
        db_table = "restapi_lead_note"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Note for Lead {self.lead_id}"
