import uuid
from django.db import models


class Lab(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=255)

    clinic = models.ForeignKey(
        "Clinic",
        on_delete=models.CASCADE,
        related_name="labs",
        null=True,
        blank=True
    )

    department = models.ForeignKey(
        "Department",
        on_delete=models.CASCADE,
        related_name="labs",
        null=True,
        blank=True
    )

    assigned_to = models.ForeignKey(
        "Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_labs"
    )

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
