from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse

from restapi.models import (
    Clinic,
    Department,
    Equipments,
)
from restapi.serializers import EquipmentSerializer


class TestEquipmentModule(APITestCase):

    def setUp(self):
        self.clinic = Clinic.objects.create(name="Test Clinic")
        self.department = Department.objects.create(
            clinic=self.clinic,
            name="Radiology",
            is_active=True
        )

    # =====================================================
    # SERIALIZER TESTS
    # =====================================================

    # ✅ CREATE EQUIPMENT WITH FULL DATA
    def test_equipment_serializer_create_success(self):
        data = {
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

        serializer = EquipmentSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        equipment = serializer.save(dep=self.department)

        self.assertEqual(equipment.equipment_name, "X-Ray")
        self.assertEqual(equipment.equipmentdetails_set.count(), 1)
        self.assertEqual(equipment.parameters.count(), 1)

    # ✅ EMPTY PAYLOAD IS VALID (BY DESIGN)
    def test_equipment_serializer_allows_empty_payload(self):
        serializer = EquipmentSerializer(data={})
        self.assertTrue(serializer.is_valid())

    # ❌ SAVE WITHOUT DEPARTMENT SHOULD FAIL
    def test_equipment_serializer_save_without_dep_fails(self):
        serializer = EquipmentSerializer(
            data={"equipment_name": "CT"}
        )

        self.assertTrue(serializer.is_valid())

        with self.assertRaises(KeyError):
            serializer.save()  # dep is mandatory at save-time

    # =====================================================
    # VIEW-LEVEL SANITY TEST
    # =====================================================

    # ✅ CREATE EQUIPMENT API
    def test_create_equipment_api_success(self):
        payload = {
            "equipment_name": "MRI",
            "is_active": True
        }

        url = reverse(
            "department-equipment-create",
            args=[self.department.id]
        )

        response = self.client.post(
            url,
            payload,
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Equipments.objects.count(), 1)
