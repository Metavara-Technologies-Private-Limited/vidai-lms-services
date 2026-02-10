import uuid
from django.db import models


class StageField(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    stage = models.ForeignKey(
        "PipelineStage",
        on_delete=models.CASCADE,
        related_name="fields"
    )

    field_name = models.CharField(max_length=255)

    FIELD_TYPE_CHOICES = (
        ("text", "Text"),
        ("number", "Number"),
        ("date", "Date"),
        ("dropdown", "Dropdown"),
    )
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES)

    is_mandatory = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "restapi_stage_field"