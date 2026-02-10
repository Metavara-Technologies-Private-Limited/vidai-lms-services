from rest_framework import serializers
from restapi.models import Clinic, Department
from restapi.services.clinic_service import create_clinic, update_clinic


# =========================
# Clinic Create / Update Serializer
# =========================
class ClinicSerializer(serializers.ModelSerializer):
    # department → list of departments
    department = serializers.ListField(required=False)

    class Meta:
        model = Clinic
        fields = ["id", "name", "department"]

    def create(self, validated_data):
        return create_clinic(validated_data)

    def update(self, instance, validated_data):
        return update_clinic(instance, validated_data)


# =========================
# Department Read Serializer
# =========================
class DepartmentReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name", "is_active"]


# =========================
# Clinic Read Serializer
# =========================
class ClinicReadSerializer(serializers.ModelSerializer):
    department = DepartmentReadSerializer(
        many=True,
        source="department_set"
    )

    class Meta:
        model = Clinic
        fields = ["id", "name", "department"]
