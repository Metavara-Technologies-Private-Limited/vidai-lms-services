from rest_framework.test import APITestCase
from restapi.models import Clinic, Department
from restapi.serializers import EquipmentSerializer


class TestEquipmentSerializer(APITestCase):

    def setUp(self):
        self.clinic = Clinic.objects.create(name="Test Clinic")
        self.department = Department.objects.create(
            clinic=self.clinic,
            name="Radiology",
            is_active=True
        )

    # ✅ VALID: full payload
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

    # ✅ VALID: empty payload (serializer allows it)
    def test_equipment_serializer_allows_empty_payload(self):
        serializer = EquipmentSerializer(data={})
        self.assertTrue(serializer.is_valid())

    # ❌ INVALID AT SAVE LEVEL (missing dep)
    def test_equipment_serializer_save_without_department_fails(self):
        serializer = EquipmentSerializer(data={"equipment_name": "CT"})
        self.assertTrue(serializer.is_valid())

        with self.assertRaises(KeyError):
            serializer.save()  # dep is mandatory at save-time
