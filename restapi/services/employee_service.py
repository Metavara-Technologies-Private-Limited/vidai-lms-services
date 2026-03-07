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

    # Prevent duplicate employee for same user
    if Employee.objects.filter(user=user).exists():
        raise serializers.ValidationError({
            "user_id": "Employee already exists for this user"
        })

    employee = Employee.objects.create(
        user=user,
        clinic=clinic,
        dep=department,
        emp_type=validated_data["emp_type"],
        emp_name=validated_data["emp_name"],
        email=validated_data.get("email"),
        contact_no=validated_data.get("contact_no"),
    )

    return employee


def update_employee(employee, validated_data):
    """
    Update an existing employee's details.
    Only updates fields that are present in validated_data.
    """
    if "emp_name" in validated_data:
        employee.emp_name = validated_data["emp_name"]

    if "emp_type" in validated_data:
        employee.emp_type = validated_data["emp_type"]

    if "email" in validated_data:
        employee.email = validated_data["email"]

    if "contact_no" in validated_data:
        employee.contact_no = validated_data["contact_no"]

    if "department_id" in validated_data:
        try:
            department = Department.objects.get(id=validated_data["department_id"])
            employee.dep = department
        except Department.DoesNotExist:
            raise serializers.ValidationError({"department_id": "Invalid department_id"})

    if "clinic_id" in validated_data:
        try:
            clinic = Clinic.objects.get(id=validated_data["clinic_id"])
            employee.clinic = clinic
        except Clinic.DoesNotExist:
            raise serializers.ValidationError({"clinic_id": "Invalid clinic_id"})

    employee.save()
    return employee


def create_user(validated_data):
    return User.objects.create_user(**validated_data)