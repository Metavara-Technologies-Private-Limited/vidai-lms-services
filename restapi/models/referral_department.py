from django.db import models
from django.db.models import UniqueConstraint
from django.db.models.functions import Lower
from restapi.models.clinic import Clinic


class ReferralDepartment(models.Model):

    name = models.CharField(max_length=255)

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="referral_departments"
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "restapi_referral_department"
        ordering = ["name"]

        # ✅ Case-insensitive unique constraint
        constraints = [
            UniqueConstraint(
                Lower("name"), "clinic",
                name="unique_referral_department_per_clinic_ci"
            )
        ]

        indexes = [
            models.Index(fields=["clinic", "name"]),
        ]

    def save(self, *args, **kwargs):
        # 🔥 Clean input
        if self.name:
            self.name = self.name.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.clinic.name}"