from django.test import TestCase
from rest_framework.exceptions import ValidationError

from restapi.models import (
    Clinic, Department, Equipments,
    Parameters, ParameterValues
)
from restapi.serializers import (
    ClinicSerializer,
    EquipmentSerializer
)


class SerializerUnitTestCase(TestCase):
    """
    These tests validate ONLY serializers.py logic.
    Views are NOT involved here.
    """

    def setUp(self):
        """
        This method runs before every test.
        Creates base objects required for serializer testing.
        """

        self.clinic = Clinic.objects.create(name="Test Clinic")

        self.department = Department.objects.create(
            clinic=self.clinic,
            name="Radiology",
            is_active=True
        )

        self.equipment = Equipments.objects.create(
            dep=self.department,
            equipment_name="CT Scanner",
            is_active=True
        )

        self.parameter = Parameters.objects.create(
            equipment=self.equipment,
            parameter_name="Voltage",
            is_active=True
        )

    # ==================================================
    # CLINIC SERIALIZER TESTS
    # ==================================================

    def test_clinic_serializer_create_success(self):
        """
        SUCCESS CASE:
        - Tests ClinicSerializer.create()
        - Creates clinic with departments and equipments
        """

        data = {
            "name": "Apollo Clinic",
            "department": [
                {
                    "name": "Cardiology",
                    "is_active": True,
                    "equipments": [
                        {
                            "equipment_name": "ECG",
                            "is_active": True
                        }
                    ]
                }
            ]
        }

        serializer = ClinicSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        clinic = serializer.save()

        self.assertEqual(clinic.name, "Apollo Clinic")
        self.assertEqual(Department.objects.filter(clinic=clinic).count(), 1)
        self.assertEqual(Equipments.objects.count(), 2)

    # ==================================================
    # EQUIPMENT SERIALIZER – CREATE
    # ==================================================

    def test_equipment_serializer_create_success_with_format(self):
        """
        SUCCESS CASE:
        - Tests EquipmentSerializer.create()
        - Uses `format` alias for parameter values
        """

        data = {
            "equipment_name": "MRI",
            "is_active": True,
            "parameters": [
                {
                    "parameter_name": "Speed",
                    "is_active": True,
                    "format": {"unit": "rpm"}
                }
            ]
        }

        serializer = EquipmentSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        equipment = serializer.save(dep=self.department)

        self.assertEqual(equipment.equipment_name, "MRI")
        self.assertEqual(Parameters.objects.filter(equipment=equipment).count(), 1)
        self.assertEqual(ParameterValues.objects.count(), 1)

    def test_equipment_serializer_create_fails_without_values(self):
        """
        ERROR CASE:
        - parameter_values and format both missing
        - Should raise ValidationError
        """

        data = {
            "equipment_name": "MRI",
            "parameters": [
                {
                    "parameter_name": "Speed"
                }
            ]
        }

        serializer = EquipmentSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        with self.assertRaises(ValidationError):
            serializer.save(dep=self.department)

    # ==================================================
    # EQUIPMENT SERIALIZER – UPDATE
    # ==================================================

    def test_equipment_serializer_update_success(self):
        """
        SUCCESS CASE:
        - Tests EquipmentSerializer.update()
        - Appends new parameter values
        """

        data = {
            "parameters": [
                {
                    "id": self.parameter.id,
                    "parameter_values": [
                        {"content": {"value": 120}}
                    ]
                }
            ]
        }

        serializer = EquipmentSerializer(
            self.equipment,
            data=data,
            partial=True
        )

        self.assertTrue(serializer.is_valid())
        serializer.save()

        self.assertEqual(
            ParameterValues.objects.filter(parameter=self.parameter).count(),
            1
        )

    def test_equipment_serializer_update_fails_without_param_id(self):
        """
        ERROR CASE:
        - parameter id missing during update
        """

        data = {
            "parameters": [
                {
                    "parameter_values": [
                        {"content": {"value": 120}}
                    ]
                }
            ]
        }

        serializer = EquipmentSerializer(
            self.equipment,
            data=data,
            partial=True
        )

        self.assertTrue(serializer.is_valid())

        with self.assertRaises(ValidationError):
            serializer.save()

    def test_equipment_serializer_update_fails_invalid_param_id(self):
        """
        ERROR CASE:
        - parameter id does not belong to this equipment
        """

        data = {
            "parameters": [
                {
                    "id": 9999,
                    "parameter_values": [
                        {"content": {"value": 120}}
                    ]
                }
            ]
        }

        serializer = EquipmentSerializer(
            self.equipment,
            data=data,
            partial=True
        )

        self.assertTrue(serializer.is_valid())

        with self.assertRaises(ValidationError):
            serializer.save()

    def test_equipment_serializer_update_fails_empty_values(self):
        """
        ERROR CASE:
        - parameter_values is empty list
        """

        data = {
            "parameters": [
                {
                    "id": self.parameter.id,
                    "parameter_values": []
                }
            ]
        }

        serializer = EquipmentSerializer(
            self.equipment,
            data=data,
            partial=True
        )

        self.assertTrue(serializer.is_valid())

        with self.assertRaises(ValidationError):
            serializer.save()
