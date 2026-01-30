from django.db import models
from .equipment import Equipments, EquipmentDetails

class Parameters(models.Model):
    equipment = models.ForeignKey(
        Equipments,
        on_delete=models.CASCADE,
        related_name="parameters"
    )
    parameter_name = models.CharField(max_length=200)
    config = models.JSONField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)


class ParameterValues(models.Model):
    parameter = models.ForeignKey(
        Parameters,
        on_delete=models.CASCADE,
        related_name="parameter_values"
    )
    equipment_details = models.ForeignKey(
        EquipmentDetails,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    content = models.TextField()
    log_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
