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

    # =============================
    # STAGE
    # =============================
    stage = models.ForeignKey(
        "restapi.PipelineStage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads"
    )

    converted_at_stage = models.ForeignKey(
        "restapi.PipelineStage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="converted_leads"
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

    gender = models.CharField(max_length=10, choices=LeadChoices.GENDER, null=True, blank=True)
    marital_status = models.CharField(max_length=20, choices=LeadChoices.MARITAL_STATUS, null=True, blank=True)

    email = models.EmailField(null=True, blank=True)
    contact_no = models.CharField(max_length=20, null=True, blank=True)

    language_preference = models.CharField(max_length=50, blank=True)
    location = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)

    # =============================
    # CONTACT INFORMATION
    # =============================
    contact_full_name = models.CharField(max_length=255, null=True, blank=True)
    contact_designation = models.CharField(max_length=255, null=True, blank=True)
    contact_phone = models.CharField(max_length=20, null=True, blank=True)
    contact_email = models.EmailField(null=True, blank=True)

    # =============================
    # PARTNER DETAILS
    # =============================
    partner_inquiry = models.BooleanField(default=False)
    partner_full_name = models.CharField(max_length=255, blank=True)
    partner_age = models.IntegerField(null=True, blank=True)
    partner_gender = models.CharField(max_length=10, choices=LeadChoices.GENDER, null=True, blank=True)

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
    # STATUS
    # =============================
    lead_status = models.CharField(max_length=100, null=True, blank=True)
    next_action_status = models.CharField(max_length=100, null=True, blank=True)
    next_action_type = models.CharField(max_length=200, null=True, blank=True)
    next_action_description = models.TextField(null=True, blank=True)

    # =============================
    # APPOINTMENT
    # =============================
    treatment_interest = models.TextField()
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

    # =============================
    # CONVERSION TIME
    # =============================
    converted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "restapi_lead"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.lead_status})"

    # =====================================================
    # ✅ FINAL SAFE SAVE LOGIC
    # =====================================================
    def save(self, *args, **kwargs):

        is_create = self._state.adding
        old_stage = None

        # =============================
        # FETCH OLD STAGE (UPDATE CASE)
        # =============================
        if not is_create:
            old = Lead.objects.filter(pk=self.pk).only("stage").first()
            old_stage = old.stage if old else None

        # =============================
        # SYNC STATUS WITH STAGE
        # =============================
        if self.stage:
            self.lead_status = self.stage.stage_name

        # =============================
        # HANDLE STAGE CHANGE (FALLBACK)
        # =============================
        if (
            not is_create
            and old_stage
            and self.stage
            and old_stage.id != self.stage.id
        ):
            if getattr(self.stage, "is_conversion_stage", False):

                # Set conversion time if not already set
                if not self.converted_at:
                    self.converted_at = timezone.now()

                # Store previous stage ONLY if not already set by API
                if not self.converted_at_stage:
                    self.converted_at_stage = old_stage

        super().save(*args, **kwargs)