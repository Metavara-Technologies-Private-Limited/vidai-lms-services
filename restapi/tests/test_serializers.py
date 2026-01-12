"""
Unit tests for serializers.py
Framework: Django unittest (TestCase)
"""

from django.test import TestCase

from rest_framework import serializers
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from django.contrib.auth import get_user_model

from restapi.models import (
    Clinic,
    Department,
    Employee,
    Equipments,
    EquipmentDetails,
    Parameters,
    Task,
    SubTask,
    Document,
    Event,
)
from restapi.serializers import (
    EquipmentSerializer,
    DepartmentSerializer,
    ClinicSerializer,
    TaskSerializer,
    TaskActivateSerializer,
    EquipmentActivateSerializer,
    EmployeeCreateSerializer,
)

User = get_user_model()

# -----------------------------
# STATUS CONSTANTS (INTEGER)
# -----------------------------
STATUS_PENDING = 0
STATUS_ACTIVE = 1
STATUS_INACTIVE = 2


class SerializerTestCase(TestCase):
    """Base setup for serializer tests"""

    def setUp(self):
        # User
        self.user = User.objects.create_user(
            username="testuser",
            password="pass123"
        )

        # Clinic
        self.clinic = Clinic.objects.create(name="Test Clinic")

        # Department
        self.department = Department.objects.create(
            clinic=self.clinic,
            name="Radiology",
            is_active=True
        )

        # Employee
        self.employee = Employee.objects.create(
            user=self.user,
            clinic=self.clinic,
            dep=self.department,
            emp_type="Technician",
            emp_name="John"
        )

        # ✅ Event (ONLY VALID FIELDS)
        self.event = Event.objects.create(
            department=self.department,
            assignment=self.employee
        )


# =====================================================
# EQUIPMENT SERIALIZER
# =====================================================

class EquipmentSerializerTest(SerializerTestCase):

    def test_create_equipment_with_details_and_parameters(self):
        """EquipmentSerializer CREATE"""

        payload = {
            "equipment_name": "X-Ray",
            "is_active": True,
            "equipment_details": [
                {
                    "equipment_num": "EQ-1",
                    "make": "GE",
                    "model": "X100",
                    "is_active": True
                }
            ],
            "parameters": [
                {
                    "parameter_name": "Voltage",
                    "is_active": True,
                    "config": {"min": 10}
                }
            ]
        }

        serializer = EquipmentSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        equipment = serializer.save(dep=self.department)

        self.assertEqual(equipment.equipment_name, "X-Ray")
        self.assertEqual(equipment.equipmentdetails_set.count(), 1)
        self.assertEqual(equipment.parameters.count(), 1)

    def test_update_parameter_without_id_fails(self):
        """Equipment update requires parameter ID"""

        equipment = Equipments.objects.create(
            dep=self.department,
            equipment_name="CT",
            is_active=True
        )

        payload = {
            "parameters": [
                {"parameter_name": "Temp"}  # ❌ no id
            ]
        }

        serializer = EquipmentSerializer(
            instance=equipment,
            data=payload,
            partial=True
        )

        self.assertTrue(serializer.is_valid())

        with self.assertRaises(ValidationError):
            serializer.save()


# =====================================================
# DEPARTMENT SERIALIZER
# =====================================================

class DepartmentSerializerTest(SerializerTestCase):

    def test_department_update_requires_equipment_id(self):
        """Department update must include equipment ID"""

        payload = {
            "equipments": [
                {"equipment_name": "MRI"}  # ❌ missing id
            ]
        }

        serializer = DepartmentSerializer(
            instance=self.department,
            data=payload,
            partial=True
        )

        self.assertTrue(serializer.is_valid())

        with self.assertRaises(ValidationError):
            serializer.save()


# =====================================================
# CLINIC SERIALIZER
# =====================================================

class ClinicSerializerTest(TestCase):

    def test_create_clinic_with_nested_data(self):
        """ClinicSerializer CREATE"""

        payload = {
            "name": "Main Clinic",
            "department": [
                {
                    "name": "Lab",
                    "equipments": [
                        {
                            "equipment_name": "Microscope",
                            "parameters": [
                                {
                                    "parameter_name": "Zoom",
                                    "config": {"level": 5}
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        serializer = ClinicSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        clinic = serializer.save()

        self.assertEqual(clinic.department_set.count(), 1)
        self.assertEqual(
            clinic.department_set.first().equipments_set.count(),
            1
        )


# =====================================================
# TASK SERIALIZER
# =====================================================

class TaskSerializerTest(SerializerTestCase):

    def test_task_create_with_subtask_and_document(self):
        """TaskSerializer CREATE"""

        payload = {
            "event": self.event.id,
            "assignment": self.employee.id,
            "due_date": timezone.now(),
            "description": "Main Task",
            "status": STATUS_PENDING,
            "sub_tasks": [
                {
                    "sub_task_due_date": timezone.now(),
                    "description": "Sub Task",
                    "status": STATUS_PENDING
                }
            ],
            "documents": [
                {
                    "document_name": "manual.pdf",
                    "data": "filedata"
                }
            ]
        }

        serializer = TaskSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        task = serializer.save()

        self.assertEqual(task.subtask_set.count(), 1)
        self.assertEqual(task.document_set.count(), 1)


# =====================================================
# ACTIVATE SERIALIZERS
# =====================================================

class TaskActivateSerializer(serializers.Serializer):
    task_id = serializers.IntegerField()

    def validate(self, attrs):
        try:
            task = Task.objects.get(id=attrs["task_id"])
        except Task.DoesNotExist:
            raise ValidationError("Invalid task id")

        attrs["task"] = task
        return attrs

    def save(self):
        task = self.validated_data["task"]

        # ✅ FIX: use INTEGER status
        task.status = Task.STATUS_ACTIVE
        task.save(update_fields=["status"])

        return task



# =====================================================
# EMPLOYEE CREATE SERIALIZER
# =====================================================

class EmployeeCreateSerializerTest(SerializerTestCase):

    def test_duplicate_employee_fails(self):
        """Duplicate employee for same user"""

        payload = {
            "user_id": self.user.id,
            "clinic_id": self.clinic.id,
            "department_id": self.department.id,
            "emp_type": "Doctor",
            "emp_name": "Duplicate"
        }

        serializer = EmployeeCreateSerializer(data=payload)

        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)
            serializer.save()
