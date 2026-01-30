from django.db import transaction

from restapi.models import (
    Clinic,
    Department,
    Equipments,
    EquipmentDetails,
    Parameters,
)


# =========================
# CREATE CLINIC
# =========================
@transaction.atomic
def create_clinic(validated_data):
    # Extract departments data from request payload
    departments_data = validated_data.pop("department", [])

    # Create clinic record
    clinic = Clinic.objects.create(**validated_data)

    # Loop through each department sent in payload
    for department_data in departments_data:

        # Create department under this clinic
        department_instance = Department.objects.create(
            clinic=clinic,
            name=department_data["name"],
            is_active=department_data.get("is_active", True),
        )

        # Create equipments under the department
        for equipment_data in department_data.get("equipments", []):
            _create_equipment(
                equipment_data,
                department_instance
            )

    return clinic


# =========================
# UPDATE CLINIC
# =========================
@transaction.atomic
def update_clinic(instance, validated_data):
    # Extract departments data from request payload
    departments_data = validated_data.pop("department", [])

    # Update clinic name if provided
    instance.name = validated_data.get("name", instance.name)
    instance.save()

    # Loop through departments sent in payload
    for department_data in departments_data:
        department_id = department_data.get("id")

        if department_id:
            # Update existing department
            department_instance = Department.objects.get(
                id=department_id,
                clinic=instance
            )
            department_instance.name = department_data.get(
                "name", department_instance.name
            )
            department_instance.is_active = department_data.get(
                "is_active", department_instance.is_active
            )
            department_instance.save()
        else:
            # Create new department if ID not provided
            department_instance = Department.objects.create(
                clinic=instance,
                name=department_data["name"],
                is_active=department_data.get("is_active", True),
            )

        # Update or create equipments under this department
        for equipment_data in department_data.get("equipments", []):
            _update_or_create_equipment(
                equipment_data,
                department_instance
            )

    return instance


# =========================
# HELPER: CREATE EQUIPMENT
# =========================
def _create_equipment(self_equipment_data, department_instance):
    equipment_data = self_equipment_data

    # Create equipment under given department
    equipment_instance = Equipments.objects.create(
        dep=department_instance,
        equipment_name=equipment_data["equipment_name"],
        is_active=equipment_data.get("is_active", True),
    )

    # Create equipment details (like model, make, number)
    for equipment_detail_data in equipment_data.get(
        "equipment_details", []
    ):
        EquipmentDetails.objects.create(
            equipment=equipment_instance,
            **equipment_detail_data
        )

    # Create parameters for the equipment
    for parameter_data in equipment_data.get("parameters", []):
        Parameters.objects.create(
            equipment=equipment_instance,
            parameter_name=parameter_data["parameter_name"],
            is_active=parameter_data.get("is_active", True),
            config=parameter_data.get("config"),
        )


# =========================
# UPDATE OR CREATE EQUIPMENT
# =========================
def _update_or_create_equipment(
    equipment_data,
    department_instance
):
    equipment_id = equipment_data.get("id")

    if equipment_id:
        # Update existing equipment
        equipment_instance = Equipments.objects.get(
            id=equipment_id,
            dep=department_instance
        )
        equipment_instance.equipment_name = equipment_data.get(
            "equipment_name",
            equipment_instance.equipment_name
        )
        equipment_instance.is_active = equipment_data.get(
            "is_active",
            equipment_instance.is_active
        )
        equipment_instance.save()
    else:
        # Create new equipment if ID not provided
        equipment_instance = Equipments.objects.create(
            dep=department_instance,
            equipment_name=equipment_data["equipment_name"],
            is_active=equipment_data.get("is_active", True),
        )

    # -------------------------
    # Equipment Details Update
    # -------------------------
    for equipment_detail_data in equipment_data.get(
        "equipment_details", []
    ):
        equipment_detail_id = equipment_detail_data.get("id")

        if equipment_detail_id:
            # Update existing equipment detail
            equipment_detail_instance = EquipmentDetails.objects.get(
                id=equipment_detail_id,
                equipment=equipment_instance
            )

            for field_name, field_value in equipment_detail_data.items():
                if field_name != "id":
                    setattr(
                        equipment_detail_instance,
                        field_name,
                        field_value
                    )

            equipment_detail_instance.save()
        else:
            # Create new equipment detail
            EquipmentDetails.objects.create(
                equipment=equipment_instance,
                **equipment_detail_data
            )

    # -------------------------
    # Parameters Update
    # -------------------------
    for parameter_data in equipment_data.get("parameters", []):
        parameter_id = parameter_data.get("id")

        if parameter_id:
            # Update existing parameter
            parameter_instance = Parameters.objects.get(
                id=parameter_id,
                equipment=equipment_instance
            )
            parameter_instance.parameter_name = parameter_data.get(
                "parameter_name",
                parameter_instance.parameter_name
            )
            parameter_instance.is_active = parameter_data.get(
                "is_active",
                parameter_instance.is_active
            )
            parameter_instance.config = parameter_data.get(
                "config",
                parameter_instance.config
            )
            parameter_instance.save()
        else:
            # Create new parameter
            Parameters.objects.create(
                equipment=equipment_instance,
                parameter_name=parameter_data["parameter_name"],
                is_active=parameter_data.get("is_active", True),
                config=parameter_data.get("config"),
            )
