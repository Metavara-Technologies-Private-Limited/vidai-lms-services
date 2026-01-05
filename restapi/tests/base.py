from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from restapi.models import Employee, Clinic, Department

class AuthenticatedAPITestCase(APITestCase):

    def setUp(self):
        User = get_user_model()

        # Create user
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass"
        )

        # 🔑 Authenticate client (THIS IS THE KEY)
        self.client.force_authenticate(user=self.user)

        # Required base data
        self.clinic = Clinic.objects.create(name="Test Clinic")
        self.department = Department.objects.create(
            name="Test Department",
            clinic=self.clinic
        )

        # Employee mapping (required for Event APIs)
        self.employee = Employee.objects.create(
            user=self.user,
            clinic=self.clinic,
            dep=self.department,
            emp_type="Doctor",
            emp_name="Test User"
        )
