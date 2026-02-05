from rest_framework import serializers

from restapi.models import Department, Environment
from restapi.serializers.equipment import EquipmentSerializer, EquipmentReadSerializer
from restapi.serializers.environment import EnvironmentReadSerializer

from restapi.services.department_service import (
    update_department,
)


# =====================================================
# Department Serializer
# =====================================================
class DepartmentSerializer(serializers.ModelSerializer):
    equipments = EquipmentSerializer(many=True, required=False)

    class Meta:
        model = Department
        fields = ["id", "name", "is_active", "equipments"]

    def update(self, instance, validated_data):
        return update_department(instance, validated_data)


class DepartmentReadSerializer(serializers.ModelSerializer):
    equipments = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = ['id', 'name', 'is_active', 'equipments']

    def get_equipments(self, obj):
        qs = (
            obj.equipments_set
            .filter(is_deleted=False)
            .prefetch_related(
                "equipmentdetails_set",
                "parameters",
          
            )
        )
        return EquipmentReadSerializer(qs, many=True).data


class DepartmentWithEnvironmentReadSerializer(serializers.ModelSerializer):
    equipments = serializers.SerializerMethodField()
    environments = serializers.SerializerMethodField()  # ✅ CHANGED

    class Meta:
        model = Department
        fields = [
            "id",
            "name",
            "is_active",
            "equipments",
            "environments",   # ✅ CHANGED
        ]

    def get_equipments(self, obj):
        qs = (
            obj.equipments_set
            .filter(is_deleted=False)
            .prefetch_related(
                "equipmentdetails_set",
                "parameters"
            )
        )
        return EquipmentReadSerializer(qs, many=True).data

    def get_environments(self, obj):
        environments = (
            Environment.objects
            .filter(
                dep=obj,
                is_deleted=False
            )
            .order_by("-created_at")        # latest first
            .prefetch_related("parameters")
        )

        return EnvironmentReadSerializer(environments, many=True).data
