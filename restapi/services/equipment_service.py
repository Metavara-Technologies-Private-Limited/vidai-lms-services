from django.db import transaction
from rest_framework.exceptions import ValidationError

from restapi.models import Equipments, EquipmentDetails, Parameters


# ==================================================
# CREATE (POST)
# ==================================================
@transaction.atomic
def create_equipment(validated_data):
    equipment_details_data = validated_data.pop("equipment_details", [])
    parameters_data = validated_data.pop("parameters", [])
    department = validated_data.pop("dep")

    equipment = Equipments.objects.create(
        dep=department,
        **validated_data
    )

    for detail in equipment_details_data:
        EquipmentDetails.objects.create(
            equipment=equipment,
            **detail
        )

    for param in parameters_data:
        Parameters.objects.create(
            equipment=equipment,
            parameter_name=param["parameter_name"],
            is_active=param.get("is_active", True),
            config=param.get("config"),
        )

    equipment.refresh_from_db()
    return equipment


# ==================================================
# UPDATE (PUT ONLY – CONTROLLED)
# ==================================================
@transaction.atomic
def update_equipment(instance, validated_data):
    equipment_details_data = validated_data.pop("equipment_details", [])
    parameters_data = validated_data.pop("parameters", [])

    # ----------------------------
    # Update Equipment (ONLY IF SENT)
    # ----------------------------
    if "equipment_name" in validated_data:
        instance.equipment_name = validated_data["equipment_name"]

    if "is_active" in validated_data:
        instance.is_active = validated_data["is_active"]

    instance.save()

    # ==================================================
    # EquipmentDetails (STRICT)
    # ==================================================
    for detail in equipment_details_data:
        detail_id = detail.get("id")

        if detail_id is not None:
            try:
                detail_instance = EquipmentDetails.objects.get(
                    id=detail_id,
                    equipment=instance
                )
            except EquipmentDetails.DoesNotExist:
                raise ValidationError(
                    f"Invalid equipment_details id {detail_id} for this equipment"
                )

            for field, value in detail.items():
                if field != "id":
                    setattr(detail_instance, field, value)

            detail_instance.save()

        else:
            EquipmentDetails.objects.create(
                equipment=instance,
                **detail
            )

    # ==================================================
    # Parameters (STRICT)
    # ==================================================
    for param in parameters_data:
        param_id = param.get("id")

        if param_id is not None:
            try:
                param_instance = Parameters.objects.get(
                    id=param_id,
                    equipment=instance
                )
            except Parameters.DoesNotExist:
                raise ValidationError(
                    f"Invalid parameter id {param_id} for this equipment"
                )

            param_instance.parameter_name = param.get(
                "parameter_name",
                param_instance.parameter_name
            )
            param_instance.is_active = param.get(
                "is_active",
                param_instance.is_active
            )

            if "config" in param:
                param_instance.config = param["config"]

            param_instance.save()

        else:
            Parameters.objects.create(
                equipment=instance,
                parameter_name=param["parameter_name"],
                is_active=param.get("is_active", True),
                config=param.get("config"),
            )

    instance.refresh_from_db()
    return instance
