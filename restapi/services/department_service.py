from django.db import transaction
from rest_framework import serializers

from restapi.models import Department, Equipments
from restapi.serializers.equipment import EquipmentSerializer


@transaction.atomic
def update_department(instance, validated_data):
    # equipments_data → list of equipment dictionaries sent from FE
    equipments_data = validated_data.pop("equipments", [])

    # Update department fields
    instance.name = validated_data.get("name", instance.name)
    instance.is_active = validated_data.get(
        "is_active", instance.is_active
    )
    instance.save()

    # ----------------------------------------------
    # Equipment Updates (Clinic / Department level)
    # ----------------------------------------------
    for equipment_data in equipments_data:

        # equipment_id → primary key of equipment
        equipment_id = equipment_data.get("id")
        if not equipment_id:
            raise serializers.ValidationError(
                "Equipment ID is required for clinic-level update"
            )

        # Fetch equipment belonging to this department
        equipment_instance = Equipments.objects.get(
            id=equipment_id,
            dep=instance
        )

        # Use replace_mode=True to fully overwrite parameter config
        equipment_serializer = EquipmentSerializer(
            instance=equipment_instance,
            data=equipment_data,
            replace_mode=True
        )

        equipment_serializer.is_valid(raise_exception=True)
        equipment_serializer.save()

    return instance
