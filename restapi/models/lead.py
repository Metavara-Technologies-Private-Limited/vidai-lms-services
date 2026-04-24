import uuid
from django.db import models
from django.utils import timezone

from .clinic import Clinic
from .department import Department
from .campaign import Campaign


class LeadChoices:

    MARITAL_STATUS = (
        ("single", "Single"),
        ("married", "Married"),
    )

    GENDER = (
        ("male", "Male"),
        ("female", "Female"),
    )

    # NEXT_ACTION_TYPE intentionally removed.
    # next_action_type is now free text driven by pipeline stage rules
    # (action_type enum or custom_label). Removing choices allows any
    # value from the pipeline to be stored without validation errors.


class Lead(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="leads")

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads"
    )

    department = models.ForeignKey(Department, on_delete=models.CASCADE)

    # ✅ SOURCE OF TRUTH
    stage = models.ForeignKey(
        "restapi.PipelineStage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads"
    )

    # =============================
    # EMPLOYEE DETAILS
    # =============================

    assigned_to_id = models.IntegerField(null=True, blank=True)
    assigned_to_name = models.CharField(max_length=255, null=True, blank=True)

    personal_id = models.IntegerField(null=True, blank=True)
    personal_name = models.CharField(max_length=255, null=True, blank=True)

    created_by_id = models.IntegerField(null=True, blank=True)
    created_by_name = models.CharField(max_length=255, null=True, blank=True)

    updated_by_id = models.IntegerField(null=True, blank=True)
    updated_by_name = models.CharField(max_length=255, null=True, blank=True)

    # =============================
    # BASIC DETAILS
    # =============================

    full_name = models.CharField(max_length=255)
    age = models.IntegerField(null=True, blank=True)

    gender = models.CharField(
        max_length=10,
        choices=LeadChoices.GENDER,
        null=True,
        blank=True
    )

    marital_status = models.CharField(
        max_length=20,
        choices=LeadChoices.MARITAL_STATUS,
        null=True,
        blank=True
    )

    email = models.EmailField(null=True, blank=True)
    contact_no = models.CharField(max_length=20)

    language_preference = models.CharField(max_length=50, blank=True)
    location = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)

    # =============================
    # PARTNER DETAILS
    # =============================

    partner_inquiry = models.BooleanField(default=False)
    partner_full_name = models.CharField(max_length=255, blank=True)
    partner_age = models.IntegerField(null=True, blank=True)

    partner_gender = models.CharField(
        max_length=10,
        choices=LeadChoices.GENDER,
        null=True,
        blank=True
    )

    # =============================
    # SOURCE
    # =============================

    source = models.CharField(max_length=100)
    sub_source = models.CharField(max_length=100, blank=True)

    referral_department = models.ForeignKey(
        "restapi.ReferralDepartment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads"
    )

    referral_source = models.ForeignKey(
        "restapi.ReferralSource",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads"
    )

    # =============================
    # STATUS (DYNAMIC — PIPELINE DRIVEN)
    # =============================

    # No choices → accepts any pipeline stage name
    lead_status = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    # No choices → accepts any pipeline stage name
    next_action_status = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    # No choices → accepts pipeline rule action_type or custom_label free text.
    # max_length increased to 200 to accommodate longer custom labels.
    next_action_type = models.CharField(
        max_length=200,
        null=True,
        blank=True
    )

    next_action_description = models.TextField(null=True, blank=True)

    # =============================
    # APPOINTMENT
    # =============================

    treatment_interest = models.TextField(help_text="Comma separated values")

    book_appointment = models.BooleanField(default=False)
    appointment_date = models.DateField(null=True, blank=True)
    slot = models.CharField(max_length=50, blank=True)
    remark = models.TextField(blank=True)

    # =============================
    # FLAGS
    # =============================

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    # =============================
    # TIMESTAMPS
    # =============================

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    converted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "restapi_lead"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.lead_status})"

    def save(self, *args, **kwargs):

        # ✅ AUTO SYNC lead_status from stage
        if self.stage and self.stage.stage_name:
            self.lead_status = self.stage.stage_name

        # ✅ FIXED CASE BUG
        if self.lead_status == "Converted" and not self.converted_at:
            self.converted_at = timezone.now()

        if self.lead_status != "Converted":
            self.converted_at = None

        super().save(*args, **kwargs)