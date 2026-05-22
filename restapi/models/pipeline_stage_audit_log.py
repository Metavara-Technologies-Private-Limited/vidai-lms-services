import uuid
from django.db import models


class PipelineStageAuditLog(models.Model):

    ACTION_CHOICES = (
        ("created", "Created"),
        ("deleted", "Deleted"),
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    pipeline = models.ForeignKey(
        "Pipeline",
        on_delete=models.CASCADE,
        related_name="stage_audit_logs"
    )

    # storing stage UUID even after deletion
    stage_id = models.UUIDField()

    stage_name = models.CharField(max_length=255)

    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES
    )

    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "restapi_pipeline_stage_audit_log"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.stage_name} - {self.action}"