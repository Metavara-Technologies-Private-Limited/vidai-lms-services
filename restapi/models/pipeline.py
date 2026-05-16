import uuid
from django.db import models
from django.db.models import Q


class Pipeline(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    clinic = models.ForeignKey(
        "Clinic",
        on_delete=models.CASCADE,
        related_name="pipelines"
    )

    pipeline_name = models.CharField(max_length=255)

    INDUSTRY_CHOICES = (
        ("healthcare", "Healthcare"),
        ("ivf", "IVF & Fertility"),
        ("pharma", "Pharma / Biotech"),
        ("diagnostics", "Diagnostics Lab"),
        ("corporate", "Corporate Sales"),
        ("education", "Education / Training"),
        ("saas", "SaaS / Technology"),
        ("manufacturing", "Manufacturing"),
        ("research", "Research"),
        ("government", "Government"),
        ("other", "Other"),
    )
    industry_type = models.CharField(max_length=50, choices=INDUSTRY_CHOICES)

    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["clinic"],
                condition=Q(is_default=True),
                name="uniq_default_pipeline_per_clinic",
            )
        ]
        db_table = "restapi_pipeline"
