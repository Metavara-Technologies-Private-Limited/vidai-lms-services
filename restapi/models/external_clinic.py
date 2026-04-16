from django.db import models
from restapi.models.clinic import Clinic


class ExternalClinic(models.Model):

    name = models.CharField(max_length=255)

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="external_clinics"
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "restapi_external_clinic"

    def __str__(self):
        return self.name