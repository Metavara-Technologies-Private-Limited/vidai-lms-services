import uuid
from django.db import models

class PipelineStage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    pipeline = models.ForeignKey(
        "Pipeline",
        on_delete=models.CASCADE,
        related_name="stages"
    )

    stage_name = models.CharField(max_length=255)

    STAGE_TYPE_CHOICES = (
        ("lead", "Lead"),
        ("engagement", "Engagement"),
        ("conversion", "Conversion"),
        ("closure", "Closure"),
    )
    stage_type = models.CharField(max_length=20, choices=STAGE_TYPE_CHOICES)

    STAGE_STATUS_CHOICES = (
        ("open", "Open"),
        ("won", "Won"),
        ("lost", "Lost"),
    )
    stage_status = models.CharField(
        max_length=20,
        choices=STAGE_STATUS_CHOICES,
        default="open"
    )

    color_code = models.CharField(max_length=10, default="#EBFAEF")

    ENTRY_RULE_CHOICES = (
        ("manual", "Manual"),
        ("auto", "Automatic"),
    )
    entry_rule = models.CharField(max_length=20, choices=ENTRY_RULE_CHOICES)

    stage_order = models.PositiveIntegerField()

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        
        db_table = "restapi_pipeline_stage"
        ordering = ["stage_order"]
