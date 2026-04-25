from django.db import models
from django.contrib.auth.models import User
from restapi.models.clinic import Clinic
from restapi.models.external_clinic import ExternalClinic   

class ReferralSource(models.Model):

    name = models.CharField(max_length=255)

    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)

    referral_department = models.ForeignKey(
        "restapi.ReferralDepartment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referral_sources"
    )

    external_clinic = models.ForeignKey(
        "restapi.ExternalClinic",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referral_sources"
    )

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="referral_sources"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "restapi_referral_source"
        ordering = ["name"]

    def __str__(self):
        return self.name