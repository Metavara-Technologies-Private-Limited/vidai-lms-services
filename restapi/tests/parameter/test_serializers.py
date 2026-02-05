from django.test import TestCase
from rest_framework.exceptions import ValidationError

from restapi.models import (
    Parameters, Equipments, Department, Clinic
)
from restapi.serializers import ParameterSoftDeleteSerializer


class ParameterSerializerTest(TestCase):

    def setUp(self):
        clinic = Clinic.objects.create(name="Clinic")
        department = Department.objects.create(
            clinic=clinic,
            name="Lab",
            is_active=True
        )

        self.equipment = Equipments.objects.create(
            dep=department,
            equipment_name="Analyzer"
        )

        self.parameter = Parameters.objects.create(
            equipment=self.equipment,
            parameter_name="PH",
            is_active=True
        )

    def test_soft_delete_parameter_success(self):
        serializer = ParameterSoftDeleteSerializer(
            data={"parameter_id": self.parameter.id}
        )

        self.assertTrue(serializer.is_valid())
        serializer.save()

        self.parameter.refresh_from_db()
        self.assertTrue(self.parameter.is_deleted)
        self.assertFalse(self.parameter.is_active)

    def test_soft_delete_invalid_parameter_fails(self):
        serializer = ParameterSoftDeleteSerializer(
            data={"parameter_id": 999}
        )

        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)
