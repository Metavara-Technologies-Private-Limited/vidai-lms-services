from rest_framework.test import APITestCase
from restapi.serializers import ClinicSerializer
from restapi.models import Clinic

class TestClinicSerializer(APITestCase):

    # ✅ SUCCESS
    def test_clinic_serializer_valid(self):
        data = {"name": "Apollo Clinic"}
        serializer = ClinicSerializer(data=data)

        self.assertTrue(serializer.is_valid())
        clinic = serializer.save()

        self.assertEqual(clinic.name, "Apollo Clinic")

    # ❌ FAILURE – missing name
    def test_clinic_serializer_invalid(self):
        serializer = ClinicSerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)
