from rest_framework import serializers

from restapi.models import (
    Clinic,
)

from restapi.serializers.department import (
    DepartmentReadSerializer,
    DepartmentWithEnvironmentReadSerializer,
)

from restapi.services.clinic_service import (
    create_clinic,
    update_clinic,
)


# =====================================================
# Clinic Serializer
# =====================================================
class ClinicSerializer(serializers.ModelSerializer):
    # department → list of departments with nested equipments
    department = serializers.ListField(required=False)

    class Meta:
        model = Clinic
        fields = ["id", "name", "department"]

    # =========================
    # CREATE CLINIC
    # =========================
    def create(self, validated_data):
        return create_clinic(validated_data)

    # =========================
    # UPDATE CLINIC
    # =========================
    def update(self, instance, validated_data):
        return update_clinic(instance, validated_data)

# =====================================================
# Clinic Read Serializer
# =====================================================

class ClinicReadSerializer(serializers.ModelSerializer):
    department = DepartmentReadSerializer(many=True, source='department_set')

    class Meta:
        model = Clinic
        fields = ['id', 'name', 'department']

# =====================================================
# Clinic Full Hierarchy Read Serializer
# =====================================================

class ClinicFullHierarchyReadSerializer(serializers.ModelSerializer):
    department = serializers.SerializerMethodField()

    class Meta:
        model = Clinic
        fields = [
            "id",
            "name",
            "department",
        ]

    def get_department(self, obj):
        departments = (
            obj.department_set
            .filter(is_active=True)
            .prefetch_related(
                "equipments_set__equipmentdetails_set",
                "equipments_set__parameters",
                "environments__parameters",
            )
        )

        return DepartmentWithEnvironmentReadSerializer(
            departments, many=True
        ).data
