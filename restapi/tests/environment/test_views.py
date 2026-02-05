from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse

from restapi.models import Clinic, Department, Environment


class TestEnvironmentViews(APITestCase):

    def setUp(self):
        self.clinic = Clinic.objects.create(name="Clinic")
        self.department = Department.objects.create(
            clinic=self.clinic,
            name="ICU"
        )

    # ✅ CREATE ENVIRONMENT
    def test_create_environment_success(self):
        payload = {
            "environment_name": "OT Environment",
            "is_active": True,
            "parameters": [
                {"env_parameter_name": "Oxygen"}
            ]
        }

        url = reverse(
            "environment-create",
            args=[self.department.id]
        )

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Environment.objects.count(), 1)

    # ❌ INVALID DEPARTMENT
    def test_create_environment_invalid_department(self):
        url = reverse("environment-create", args=[999])

        response = self.client.post(
            url,
            {"environment_name": "Fail Env"},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ✅ GET ENVIRONMENT
    def test_get_environment_success(self):
        env = Environment.objects.create(
            dep=self.department,
            environment_name="Ward Env"
        )

        url = reverse("environment-get", args=[env.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["environment_name"],
            "Ward Env"
        )

    # ❌ GET ENVIRONMENT NOT FOUND
    def test_get_environment_not_found(self):
        url = reverse("environment-get", args=[999])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ✅ ACTIVATE ENVIRONMENT
    def test_activate_environment(self):
        env = Environment.objects.create(
            dep=self.department,
            environment_name="Inactive Env",
            is_active=False
        )

        url = reverse("environment-activate", args=[env.id])
        response = self.client.post(url)

        env.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(env.is_active)

    # ✅ INACTIVATE ENVIRONMENT
    def test_inactivate_environment(self):
        env = Environment.objects.create(
            dep=self.department,
            environment_name="Active Env",
            is_active=True
        )

        url = reverse("environment-inactivate", args=[env.id])
        response = self.client.patch(url)

        env.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(env.is_active)
