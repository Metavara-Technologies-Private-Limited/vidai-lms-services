from django.db import transaction
from restapi.models import Clinic, Department
from rest_framework.exceptions import ValidationError


# =========================
# CREATE CLINIC
# =========================
@transaction.atomic
def create_clinic(validated_data):
    departments_data = validated_data.pop("department", [])

    if not departments_data:
        raise ValidationError("At least one department is required")

    clinic = Clinic.objects.create(**validated_data)

    for department_data in departments_data:
        Department.objects.create(
            clinic=clinic,
            name=department_data["name"],
            is_active=department_data.get("is_active", True),
        )

    return clinic


# =========================
# UPDATE CLINIC
# =========================
@transaction.atomic
def update_clinic(instance, validated_data):
    departments_data = validated_data.pop("department", [])

    instance.name = validated_data.get("name", instance.name)
    instance.email = validated_data.get("email", instance.email)
    instance.save()

    for department_data in departments_data:
        department_id = department_data.get("id")

        if department_id:
            department = Department.objects.filter(
                id=department_id,
                clinic=instance
            ).first()

            if not department:
                raise ValidationError("Invalid department for this clinic")

            department.name = department_data.get("name", department.name)
            department.is_active = department_data.get("is_active", department.is_active)
            department.save()
        else:
            Department.objects.create(
                clinic=instance,
                name=department_data["name"],
                is_active=department_data.get("is_active", True),
            )

    return instance