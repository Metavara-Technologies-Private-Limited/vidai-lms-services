from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from restapi.models import Equipments, EquipmentDetails, Parameters
from restapi.serializers.parameter import ParameterSerializer, ParameterReadSerializer
from restapi.services.equipment_service import (
    create_equipment,
    update_equipment,
)

# =====================================================
# Equipment Details Serializer
# =====================================================
class EquipmentDetailSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = EquipmentDetails
        fields = [
            "id",              # ✅ MUST BE HERE
            "equipment_num",
            "make",
            "model",
            "is_active",
        ]


# =====================================================
# Equipment Serializer
# =====================================================
# This serializer is responsible for:
# - Creating equipment
# - Updating equipment
# - Handling equipment active/inactive state
# - Managing nested equipment details and parameters
class EquipmentSerializer(serializers.ModelSerializer):
    # 🔑 equipment_name OPTIONAL for PUT
    equipment_name = serializers.CharField(required=False)

    equipment_details = EquipmentDetailSerializer(many=True, required=False)
    parameters = ParameterSerializer(many=True, required=False)

    class Meta:
        model = Equipments
        fields = [
            "id",
            "equipment_name",
            "is_active",
            "equipment_details",
            "parameters",
        ]

    # ==================================================
    # CREATE (POST)
    # ==================================================
    def create(self, validated_data):
        return create_equipment(validated_data)

    # ==================================================
    # UPDATE (PUT ONLY – CONTROLLED)
    # ==================================================
    def update(self, instance, validated_data):
        return update_equipment(instance, validated_data)


# =====================================================
# Equipment Activate Serializer
# =====================================================
class EquipmentActivateSerializer(serializers.Serializer):
    equipment_id = serializers.IntegerField()

    def validate(self, attrs):
        try:
            equipment = Equipments.objects.get(
                id=attrs["equipment_id"],
                is_deleted=False
            )
        except Equipments.DoesNotExist:
            raise ValidationError("Invalid equipment id")

        attrs["equipment"] = equipment
        return attrs

    def save(self):
        equipment = self.validated_data["equipment"]
        equipment.is_active = True
        equipment.save(update_fields=["is_active"])
        return equipment


# =====================================================
# Read Serializers Equipment Related
# =====================================================
class EquipmentDetailReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentDetails
        fields = ['id', 'equipment_num', 'make', 'model', 'is_active']


class EquipmentReadSerializer(serializers.ModelSerializer):
    equipment_details = EquipmentDetailReadSerializer(
        many=True,
        source="equipmentdetails_set"
    )
    parameters = ParameterReadSerializer(many=True)

    class Meta:
        model = Equipments
        fields = [
            "id",
            "equipment_name",
            "is_active",
            "created_at", 
            "equipment_details",
            "parameters",
        ]
