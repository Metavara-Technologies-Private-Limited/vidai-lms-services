from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse

from restapi.models import Clinic, Department, Equipments


class TestClinicViews(APITestCase):

    # ✅ CREATE – SUCCESS
    def test_create_clinic_success(self):
        url = reverse("clinic-create")

        response = self.client.post(
            url,
            {"name": "Apollo"},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Clinic.objects.count(), 1)

    # ❌ CREATE – VALIDATION ERROR
    def test_create_clinic_failure(self):
        url = reverse("clinic-create")

        response = self.client.post(url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ✅ GET – SUCCESS
    def test_get_clinic_success(self):
        clinic = Clinic.objects.create(name="Apollo")

        url = reverse("clinic-get", args=[clinic.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ❌ GET – NOT FOUND
    def test_get_clinic_not_found(self):
        url = reverse("clinic-get", args=[999])

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

class TestClinicDepartmentsAPIView(APITestCase):

    def setUp(self):
        self.clinic = Clinic.objects.create(name="Apollo")

        self.department = Department.objects.create(
            clinic=self.clinic,
            name="OT",
            is_active=True
        )

        self.equipment = Equipments.objects.create(
            dep=self.department,
            equipment_name="Monitor"
        )

        self.url = reverse(
            "clinic-departments",
            args=[self.clinic.id]
        )

    # ✅ GET – SUCCESS
    def test_get_clinic_departments_success(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["clinic_id"], self.clinic.id)
        self.assertEqual(response.data["clinic_name"], self.clinic.name)
        self.assertEqual(len(response.data["departments"]), 1)

    # ❌ GET – CLINIC NOT FOUND
    def test_get_clinic_departments_not_found(self):
        url = reverse("clinic-departments", args=[999])

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)