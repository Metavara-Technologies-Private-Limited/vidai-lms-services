"""
View Tests for restapi
Framework: Django unittest (TestCase)
Single file – NO separate setup
Covers: 200, 201, 400, 404
"""

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from rest_framework.test import APIClient
from rest_framework import status

from restapi.models import (
    Clinic,
    Department,
    Equipments,
    EquipmentDetails,
    Parameters,
    ParameterValues,
    Employee,
    Event,
    Task,
    SubTask,
    Document,
)

User = get_user_model()


# =====================================================
# BASE SETUP
# =====================================================
class BaseViewTestCase(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create_user(
            username="testuser",
            password="pass123"
        )

        self.clinic = Clinic.objects.create(name="Test Clinic")

        self.department = Department.objects.create(
            name="Radiology",
            clinic=self.clinic
        )

        self.employee = Employee.objects.create(
            user=self.user,
            dep=self.department,
            clinic=self.clinic,
            emp_type="Technician",
            emp_name="John"
        )

        self.equipment = Equipments.objects.create(
            equipment_name="X-Ray",
            dep=self.department
        )

        self.equipment_detail = EquipmentDetails.objects.create(
            equipment=self.equipment,
            equipment_num="EQ-001",
            make="GE",
            model="XR-100"
        )

        self.parameter = Parameters.objects.create(
            equipment=self.equipment,
            parameter_name="Voltage",
            config={"min": 10}
        )

        self.event = Event.objects.create(
            department=self.department,
            assignment=self.employee,
            event_name="Monthly Maintenance",
            description="Routine check"
        )

        self.task = Task.objects.create(
            event=self.event,
            assignment=self.employee,
            due_date=timezone.now(),
            description="Check voltage",
            status=Task.TODO
        )

        self.subtask = SubTask.objects.create(
            task=self.task,
            assignment=self.employee,
            due_date=timezone.now(),
            description="Measure voltage",
            status=Task.TODO
        )

        self.document = Document.objects.create(
            task=self.task,
            document_name="report.pdf",
            data=b"dummy-data"
        )

        self.parameter_value = ParameterValues.objects.create(
            parameter=self.parameter,
            equipment_details=self.equipment_detail,
            content="120"
        )


# =====================================================
# CLINIC APIs
# =====================================================
class ClinicAPIViewTest(BaseViewTestCase):

    def test_create_clinic_201(self):
        response = self.client.post(
            "/clinics",
            {"name": "New Clinic"},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_clinic_400(self):
        response = self.client.post(
            "/clinics",
            {},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_clinic_200(self):
        response = self.client.get(
            f"/get_clinic/{self.clinic.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_clinic_404(self):
        response = self.client.get("/get_clinic/99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# =====================================================
# EQUIPMENT APIs
# =====================================================
class EquipmentAPIViewTest(BaseViewTestCase):

    def test_create_equipment_201(self):
        response = self.client.post(
            f"/departments/{self.department.id}/equipments/",
            {"equipment_name": "CT"},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_equipment_400(self):
        response = self.client.post(
            f"/departments/{self.department.id}/equipments/",
            {},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_equipment_department_404(self):
        response = self.client.post(
            "/departments/99999/equipments/",
            {"equipment_name": "CT"},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_inactivate_equipment_200(self):
        response = self.client.patch(
            f"/departments/{self.department.id}/equipments/{self.equipment.id}/inactive/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_inactivate_equipment_404(self):
        response = self.client.patch(
            f"/departments/{self.department.id}/equipments/99999/inactive/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_soft_delete_equipment_200(self):
        response = self.client.patch(
            f"/departments/{self.department.id}/equipments/{self.equipment.id}/delete/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_soft_delete_equipment_404(self):
        response = self.client.patch(
            f"/departments/{self.department.id}/equipments/99999/delete/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# =====================================================
# TASK APIs
# =====================================================
class TaskAPIViewTest(BaseViewTestCase):

    def test_create_task_201(self):
        response = self.client.post(
            "/tasks",
            {
                "event": self.event.id,
                "assignment": self.employee.id,
                "due_date": timezone.now(),
                "description": "New Task",
                "status": Task.TODO,
            },
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_task_400(self):
        response = self.client.post("/tasks", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_task_200(self):
        response = self.client.get(f"/tasks/{self.task.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_task_404(self):
        response = self.client.get("/tasks/99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_soft_delete_task_200(self):
        response = self.client.patch(f"/tasks/{self.task.id}/delete/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_soft_delete_task_404(self):
        response = self.client.patch("/tasks/99999/delete/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_soft_delete_subtask_200(self):
        response = self.client.patch(
            f"/subtasks/{self.subtask.id}/delete/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_soft_delete_subtask_404(self):
        response = self.client.patch("/subtasks/99999/delete/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# =====================================================
# PARAMETER VALUE APIs
# =====================================================
class ParameterValueAPIViewTest(BaseViewTestCase):

    def test_create_parameter_value_201(self):
        response = self.client.post(
            "/parameter-values/",
            {
                "parameter": self.parameter.id,
                "equipment_details": self.equipment_detail.id,
                "content": "135",
            },
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_parameter_value_400(self):
        response = self.client.post(
            "/parameter-values/",
            {},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_parameter_value_404(self):
        response = self.client.get(
            "/parameters/99999/values/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
