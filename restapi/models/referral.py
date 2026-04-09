# restapi/models/referral.py

from django.db import models
from django.contrib.auth.models import User
from restapi.models.clinic import Clinic


# 🔹 External Clinics (Doctors belong here)
class ExternalClinic(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


# 🔹 Referral Source (Doctor / HR / Lab etc.)
class ReferralSource(models.Model):

    TYPE_CHOICES = [
        ("doctor", "Doctor"),
        ("corporate_hr", "Corporate HR"),
        ("insurance", "Insurance"),
        ("lab", "Diagnostic Lab"),
        ("partner", "Partner"),
    ]

    name = models.CharField(max_length=255)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)

    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)

    # 👉 External clinic (Doctor's hospital)
    external_clinic = models.ForeignKey(
        ExternalClinic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referral_sources"
    )

    # 👉 Your system clinic (Crysta IVF)
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="referral_sources"
    )

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.type})"