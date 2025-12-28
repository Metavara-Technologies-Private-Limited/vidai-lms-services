from rest_framework.test import APITestCase
from restapi.models import Clinic, Department


class BaseAPITestCase(APITestCase):

    def setUp(self):
        self.clinic = Clinic.objects.create(
            name="Test Clinic"
        )

        self.department = Department.objects.create(
            clinic=self.clinic,
            name="Radiology",
            is_active=True
        )
