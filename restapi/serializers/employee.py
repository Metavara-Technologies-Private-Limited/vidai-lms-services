from rest_framework import serializers
from django.contrib.auth import get_user_model

from restapi.models import Employee, Clinic, Department
from restapi.services.employee_service import (
    create_employee,
    create_user,
)

User = get_user_model()


# =========================
# Employee Create Serializer
# =========================
class EmployeeCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    clinic_id = serializers.IntegerField()
    department_id = serializers.IntegerField()
    emp_type = serializers.CharField(max_length=100)
    emp_name = serializers.CharField(max_length=200)

    def create(self, validated_data):
        return create_employee(validated_data)


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


class EmployeeReadSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="dep.name", read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "emp_name",
            "emp_type",
            "department_name"
        ]
