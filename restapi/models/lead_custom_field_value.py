import uuid

from django.db import models


class LeadCustomFieldValue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(
        "Lead",
        on_delete=models.CASCADE,
        related_name="custom_field_values",
    )
    field = models.ForeignKey(
        "LeadFormField",
        on_delete=models.CASCADE,
        related_name="lead_values",
    )
    value = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "restapi_lead_custom_field_value"
        unique_together = ("lead", "field")
        indexes = [
            models.Index(fields=["lead", "field"]),
        ]

    def __str__(self):
        return f"{self.lead_id}:{self.field_id}"
