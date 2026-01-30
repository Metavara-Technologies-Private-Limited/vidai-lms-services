from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from restapi.models import Clinic, Department, Employee
from django.contrib.auth import get_user_model

User = get_user_model()


class EventAPIViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()

        # User
        self.user = User.objects.create_user(
            username="apiuser",
            password="pass"
        )
        self.client.force_authenticate(self.user)

        # Clinic + Department
        self.clinic = Clinic.objects.create(name="Clinic API")
        self.department = Department.objects.create(
            clinic=self.clinic,
            name="Emergency",
            is_active=True
        )

        # ✅ CREATE EMPLOYEE (THIS FIXES 500)
        self.employee = Employee.objects.create(
            user=self.user,
            clinic=self.clinic,
            dep=self.department,
            emp_name="Doctor",
            emp_type="Doctor"
        )

    def test_create_event_api_success(self):
        payload = {
            "department_id": self.department.id,
            "event_name": "API Event",
            "description": "From API",
            "schedule": {
                "type": 1,
                "from_time": "2025-01-01T10:00:00Z",
                "to_time": "2025-01-01T12:00:00Z"
            }
        }

        response = self.client.post(
            "/api/event",
            payload,
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
