# restapi/models/interest.py

import uuid
from django.db import models
from .clinic import Clinic


class Interest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="interests"
    )

    name = models.CharField(max_length=255)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "restapi_interest"
        unique_together = ("clinic", "name")

    def __str__(self):
        return self.name