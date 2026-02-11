import uuid
from django.db import models
from django.utils import timezone

from .clinic import Clinic
from .department import Department
from .employee import Employee
from .campaign import Campaign

class LeadChoices:
    """
    NOTE:
    These are initial minimal values.
    Frontend / Postman must send ONLY these string values.
    If business confirms more values later, we will extend this list.
    """

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
    )

    NEXT_ACTION_STATUS = (
        ("pending", "Pending"),
        ("completed", "Completed"),
    )


class Lead(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

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

    partner_inquiry = models.BooleanField(default=False)
    partner_full_name = models.CharField(max_length=255, blank=True)
    partner_age = models.IntegerField(null=True, blank=True)
    partner_gender = models.CharField(
        max_length=10,
        choices=LeadChoices.GENDER,
        null=True,
        blank=True
    )

    source = models.CharField(max_length=100)
    sub_source = models.CharField(max_length=100, blank=True)

    assigned_to = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        related_name="assigned_leads"
    )

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

    next_action_description = models.TextField(
        null=True,
        blank=True
    )

    treatment_interest = models.TextField(
        help_text="Comma separated values"
    )

    document = models.FileField(
        upload_to="lead_documents/",
        null=True,
        blank=True
    )

    book_appointment = models.BooleanField(default=False)

    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE
    )

    personal = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        related_name="personal_leads"
    )

    appointment_date = models.DateField()
    slot = models.CharField(max_length=50)
    remark = models.TextField(blank=True)
    

    # ✅ NEW FLAGS
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        #anaged = False          # 🔐 VERY IMPORTANT
        db_table = "restapi_lead"        # 👈 must match EXISTING DB table
