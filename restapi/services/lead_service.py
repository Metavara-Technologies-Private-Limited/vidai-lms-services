from django.db import transaction
from rest_framework.exceptions import ValidationError

from restapi.models import (
    Lead,
    Clinic,
    Department,
    Employee,
    Campaign,
)


# =====================================================
# CREATE
# =====================================================
@transaction.atomic
def create_lead(validated_data):
    try:
        clinic = Clinic.objects.get(id=validated_data.pop("clinic_id"))
    except Clinic.DoesNotExist:
        raise ValidationError({"clinic_id": "Invalid clinic_id"})

    try:
        department = Department.objects.get(
            id=validated_data.pop("department_id"),
            clinic=clinic
        )
    except Department.DoesNotExist:
        raise ValidationError({"department_id": "Invalid department_id for this clinic"})

    # ------------------------
    # Campaign
    # ------------------------
    campaign = None
    campaign_id = validated_data.pop("campaign_id", None)
    if campaign_id:
        campaign = Campaign.objects.filter(id=campaign_id).first()

    # ------------------------
    # Assigned To (STRICT)
    # ------------------------
    assigned_to = None
    assigned_to_id = validated_data.pop("assigned_to_id", None)
    if assigned_to_id:
        assigned_to = Employee.objects.filter(
            id=assigned_to_id,
            clinic=clinic
        ).first()

        if not assigned_to:
            raise ValidationError(
                "Assigned employee does not belong to this clinic"
            )

    # ------------------------
    # Personal (STRICT)
    # ------------------------
    personal = None
    personal_id = validated_data.pop("personal_id", None)
    if personal_id:
        personal = Employee.objects.filter(
            id=personal_id,
            clinic=clinic
        ).first()

        if not personal:
            raise ValidationError(
                "Personal employee does not belong to this clinic"
            )

    lead = Lead.objects.create(
        clinic=clinic,
        department=department,
        campaign=campaign,
        assigned_to=assigned_to,
        personal=personal,
        **validated_data
    )

    return lead


# =====================================================
# UPDATE (STRICT, ID SAFE)
# =====================================================
@transaction.atomic
def update_lead(instance, validated_data):
    IMMUTABLE_FIELDS = {
        "clinic",
        "department",
        "campaign",
        "clinic_id",
        "department_id",
        "campaign_id",
    }

    for field, value in validated_data.items():
        if field in IMMUTABLE_FIELDS:
            continue
        if hasattr(instance, field):
            setattr(instance, field, value)

    instance.save()
    instance.refresh_from_db()
    return instance

