from rest_framework import serializers
from django.contrib.auth import get_user_model
from restapi.utils.permissions import get_user_permissions, has_permission
from restapi.models import Employee, Clinic, Department
from restapi.services.employee_service import (
    create_employee,
    update_employee,
    create_user,
)

User = get_user_model()


# =========================
# Employee Create Serializer
# =========================
class EmployeeCreateSerializer(serializers.Serializer):
    user_id       = serializers.IntegerField()
    clinic_id     = serializers.IntegerField()
    department_id = serializers.IntegerField()
    emp_type      = serializers.CharField(max_length=100)
    emp_name      = serializers.CharField(max_length=200)
    email         = serializers.EmailField(max_length=255, required=False, allow_null=True, allow_blank=True)
    contact_no    = serializers.CharField(max_length=20,  required=False, allow_null=True, allow_blank=True)

    def create(self, validated_data):
        return create_employee(validated_data)


# =========================
# Employee Update Serializer
# =========================
class EmployeeUpdateSerializer(serializers.Serializer):
    clinic_id     = serializers.IntegerField(required=False)
    department_id = serializers.IntegerField(required=False)
    emp_type      = serializers.CharField(max_length=100, required=False)
    emp_name      = serializers.CharField(max_length=200, required=False)
    email         = serializers.EmailField(max_length=255, required=False, allow_null=True, allow_blank=True)
    contact_no    = serializers.CharField(max_length=20,  required=False, allow_null=True, allow_blank=True)

    def update(self, instance, validated_data):
        return update_employee(instance, validated_data)


# =========================
# User Create Serializer
# =========================
class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["username", "password"]

    def create(self, validated_data):
        return create_user(validated_data)


# =========================
# Employee Read Serializer
# =========================
class EmployeeReadSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="dep.name", read_only=True)
    clinic_name     = serializers.CharField(source="clinic.name", read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "emp_name",
            "emp_type",
            "department_name",
            "clinic_name",
            "email",
            "contact_no",
            "created_at",
            "modified_at",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)

        request = self.context.get("request")
        if not request:
            return data

        user = request.user

        if user.profile.role.name.lower() == "super admin":
            return data

        if not has_permission(user, "employee", "employees", "view"):
            return {}

        allowed_fields = [
            "id",
            "emp_name",
            "emp_type",
            "department_name",
            "clinic_name"
        ]

        return {k: v for k, v in data.items() if k in allowed_fields}