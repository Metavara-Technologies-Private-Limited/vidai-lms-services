import uuid
from django.db import models


class StageRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    stage = models.ForeignKey(
        "PipelineStage",
        on_delete=models.CASCADE,
        related_name="rules"
    )

    ACTION_TYPE_CHOICES = (
        ("call", "Call"),
        ("email", "Email"),
        ("whatsapp", "WhatsApp"),
        ("sms", "SMS"),
        ("appointment", "Appointment"),
        ("custom", "Custom Action"),
    )
    action_type = models.CharField(max_length=30, choices=ACTION_TYPE_CHOICES)

    is_enabled = models.BooleanField(default=True)
    is_required = models.BooleanField(default=False)

    auto_move = models.BooleanField(default=False)
    allow_manual_move = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        
        db_table = "restapi_stage_rule"
