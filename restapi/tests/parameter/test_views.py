from django.test import TestCase
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse

from restapi.models import (
    Clinic,
    Department,
    Equipments,
    Parameters,
    Environment,
    Environment_Parameter
)


class ParameterAPIViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.clinic = Clinic.objects.create(name="Clinic")
        self.department = Department.objects.create(
            clinic=self.clinic,
            name="OT",
            is_active=True
        )

        self.equipment = Equipments.objects.create(
            dep=self.department,
            equipment_name="Monitor"
        )

        self.parameter = Parameters.objects.create(
            equipment=self.equipment,
            parameter_name="ECG",
            is_active=True,
            is_deleted=False
        )

    def test_soft_delete_parameter_api(self):
        url = reverse(
            "parameter-soft-delete",
            args=[self.parameter.id]
        )

        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ParameterToggleAPIViewTest(APITestCase):

    def setUp(self):
        self.client = APIClient()

        # Clinic & Department
        self.clinic = Clinic.objects.create(name="Clinic")
        self.department = Department.objects.create(
            clinic=self.clinic,
            name="OT",
            is_active=True
        )

        # Environment (dep is REQUIRED)
        self.environment = Environment.objects.create(
            dep=self.department
        )

        # Equipment
        self.equipment = Equipments.objects.create(
            dep=self.department,
            equipment_name="Monitor"
        )

        # Equipment Parameter
        self.equipment_parameter = Parameters.objects.create(
            equipment=self.equipment,
            parameter_name="ECG",
            is_active=False,
            is_deleted=False
        )

        # Environment Parameter
        self.environment_parameter = Environment_Parameter.objects.create(
            environment=self.environment,
            env_parameter_name="Temperature",
            config={},
            is_active=False,
            is_deleted=False
        )

        self.activate_url = reverse("parameter-activate")
        self.inactivate_url = reverse("parameter-inactivate")

    def test_activate_equipment_parameter(self):
        response = self.client.post(
            self.activate_url,
            {
                "type": "equipment",
                "parameter_id": self.equipment_parameter.id
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.equipment_parameter.refresh_from_db()
        self.assertTrue(self.equipment_parameter.is_active)

    def test_inactivate_equipment_parameter(self):
        self.equipment_parameter.is_active = True
        self.equipment_parameter.save()

        response = self.client.patch(
            self.inactivate_url,
            {
                "type": "equipment",
                "parameter_id": self.equipment_parameter.id
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.equipment_parameter.refresh_from_db()
        self.assertFalse(self.equipment_parameter.is_active)

    def test_activate_environment_parameter(self):
        response = self.client.post(
            self.activate_url,
            {
                "type": "environment",
                "parameter_id": self.environment_parameter.id
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.environment_parameter.refresh_from_db()
        self.assertTrue(self.environment_parameter.is_active)

    def test_inactivate_environment_parameter(self):
        self.environment_parameter.is_active = True
        self.environment_parameter.save()

        response = self.client.patch(
            self.inactivate_url,
            {
                "type": "environment",
                "parameter_id": self.environment_parameter.id
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.environment_parameter.refresh_from_db()
        self.assertFalse(self.environment_parameter.is_active)

    def test_parameter_not_found(self):
        response = self.client.post(
            self.activate_url,
            {
                "type": "equipment",
                "parameter_id": 9999
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
