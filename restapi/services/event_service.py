from django.db import transaction
from rest_framework.exceptions import ValidationError

from restapi.models import (
    Event,
    EventSchedule,
    EventEquipment,
    EventParameter,
    Department,
    Employee,
    Equipments,
    EquipmentDetails,
    Parameters,
)


# ---------------- VALIDATION ----------------
def validate_event_create(serializer, attrs):
    # Department
    department = Department.objects.get(id=attrs["department_id"])

    # Assignment
    assignment = (
        Employee.objects.get(id=attrs["assignment_id"])
        if attrs.get("assignment_id")
        else serializer.context["request"].user.employee
    )

    equipment_details_ids = attrs.get("equipment_details_ids", [])
    parameter_ids = attrs.get("parameter_ids", [])

    # =========================
    # VALIDATE EQUIPMENT DETAILS
    # =========================
    equipment_details = EquipmentDetails.objects.filter(
        id__in=equipment_details_ids,
        equipment__dep=department,
        is_active=True
    )

    if equipment_details.count() != len(set(equipment_details_ids)):
        raise ValidationError("Invalid equipment details selection")

    # =========================
    # DERIVE EQUIPMENTS (MASTER)
    # =========================
    equipments = Equipments.objects.filter(
        id__in=equipment_details.values_list("equipment_id", flat=True),
        is_active=True,
        is_deleted=False
    )

    # =========================
    # VALIDATE PARAMETERS
    # =========================
    parameters = Parameters.objects.filter(
        id__in=parameter_ids,
        is_active=True
    )

    invalid = parameters.exclude(equipment__in=equipments)
    if invalid.exists():
        raise ValidationError(
            "Parameters must belong to selected equipments"
        )

    # Store validated objects
    attrs["department"] = department
    attrs["assignment"] = assignment
    attrs["equipment_details"] = equipment_details
    attrs["parameters"] = parameters

    return attrs


# ---------------- CREATE ----------------
@transaction.atomic
def create_event(validated_data):
    event = Event.objects.create(
        department=validated_data["department"],
        assignment=validated_data["assignment"],
        event_name=validated_data["event_name"],
        description=validated_data["description"]
    )

    # Create schedule
    EventSchedule.objects.create(
        event=event,
        **validated_data["schedule"]
    )

    # Link equipment details
    for ed in validated_data["equipment_details"]:
        EventEquipment.objects.create(
            event=event,
            equipment_details=ed
        )

    # Link parameters
    for p in validated_data["parameters"]:
        EventParameter.objects.create(
            event=event,
            parameter=p
        )

    return event
