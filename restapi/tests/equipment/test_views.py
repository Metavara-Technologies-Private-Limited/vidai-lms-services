from rest_framework.test import APITestCase
from rest_framework import status
from restapi.models import Clinic, Department, Equipments

class TestEquipmentViews(APITestCase):

    def setUp(self):
        self.clinic = Clinic.objects.create(name="Clinic")
        self.department = Department.objects.create(
            clinic=self.clinic,
            name="ICU"
        )

    # ✅ CREATE
    def test_create_equipment(self):
        response = self.client.post(
            f"/api/departments/{self.department.id}/equipments/",
            {"equipment_name": "Ventilator"},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Equipments.objects.count(), 1)

    # ❌ INVALID DEPARTMENT
    def test_create_equipment_invalid_department(self):
        response = self.client.post(
            "/api/departments/999/equipments/",
            {"equipment_name": "Ventilator"},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
