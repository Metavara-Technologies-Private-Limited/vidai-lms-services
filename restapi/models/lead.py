import uuid
from django.db import models

from .clinic import Clinic
from .department import Department
from .employee import Employee
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

    LEAD_STATUS = (
        ("new", "New"),
        ("contacted", "Contacted"),
        ("appointment", "Appointment"),
        ("follow_up", "Follow Up"),
        ("converted", "Converted"),
        ("cycle_conversion", "Cycle Conversion"),
        ("lost", "Lost"),
    )

    NEXT_ACTION_STATUS = (
        ("pending", "Pending"),
        ("completed", "Completed"),
    )

    NEXT_ACTION_TYPE = (
        ("Follow Up", "Follow Up"),
        ("Call Patient", "Call Patient"),
        ("Book Appointment", "Book Appointment"),
        ("Send Message", "Send Message"),
        ("Send Email", "Send Email"),
        ("Review Details", "Review Details"),
        ("No Action", "No Action"),
    )


class Lead(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # =============================
    # RELATIONS
    # =============================

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="leads"
    )

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads"
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE
    )

    assigned_to = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_leads"
    )

    personal = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="personal_leads"
    )

    # ✅ NEW FIELD
    created_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_leads"
    )

    # ✅ Recommended (audit purpose)
    updated_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_leads"
    )

    # =============================
    # BASIC DETAILS
    # =============================

    full_name = models.CharField(max_length=255)
    age = models.IntegerField(null=True, blank=True)

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
    # SOURCE DETAILS
    # =============================

    source = models.CharField(max_length=100)
    sub_source = models.CharField(max_length=100, blank=True)

    # =============================
    # STATUS TRACKING
    # =============================

    lead_status = models.CharField(
        max_length=20,
        choices=LeadChoices.LEAD_STATUS,
        default="new"
    )

    next_action_status = models.CharField(
        max_length=20,
        choices=LeadChoices.NEXT_ACTION_STATUS,
        null=True,
        blank=True
    )

    next_action_type = models.CharField(
        max_length=50,
        choices=LeadChoices.NEXT_ACTION_TYPE,
        null=True,
        blank=True
    )

    next_action_description = models.TextField(
        null=True,
        blank=True
    )

    # =============================
    # TREATMENT / APPOINTMENT
    # =============================

    treatment_interest = models.TextField(
        help_text="Comma separated values"
    )

    book_appointment = models.BooleanField(default=False)
    appointment_date = models.DateField(null=True, blank=True)
    slot = models.CharField(max_length=50, blank=True)
    remark = models.TextField(blank=True)

    # =============================
    # SYSTEM FLAGS
    # =============================

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    # =============================
    # TIMESTAMPS
    # =============================

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "restapi_lead"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.lead_status})"