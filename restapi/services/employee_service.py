from rest_framework import serializers
from django.contrib.auth import get_user_model

from restapi.models import Employee, Clinic, Department

User = get_user_model()


def create_employee(validated_data):
    try:
        user = User.objects.get(id=validated_data["user_id"])
    except User.DoesNotExist:
        raise serializers.ValidationError({"user_id": "Invalid user_id"})

    try:
        clinic = Clinic.objects.get(id=validated_data["clinic_id"])
    except Clinic.DoesNotExist:
        raise serializers.ValidationError({"clinic_id": "Invalid clinic_id"})

    try:
        department = Department.objects.get(id=validated_data["department_id"])
    except Department.DoesNotExist:
        raise serializers.ValidationError({"department_id": "Invalid department_id"})

    # ❗ prevent duplicate employee for same user
    if Employee.objects.filter(user=user).exists():
        raise serializers.ValidationError({
            "user_id": "Employee already exists for this user"
        })

    employee = Employee.objects.create(
        user=user,
        clinic=clinic,
        dep=department,
        emp_type=validated_data["emp_type"],
        emp_name=validated_data["emp_name"]
    )

    return employee


def create_user(validated_data):
    return User.objects.create_user(**validated_data)
