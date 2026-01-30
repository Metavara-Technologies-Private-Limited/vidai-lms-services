from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from restapi.models import (
    Clinic, Department, Employee,
    Task, SubTask, Document, Task_Event
)
from restapi.serializers import TaskSerializer
from django.contrib.auth import get_user_model

User = get_user_model()

STATUS_PENDING = 0


class TaskSerializerTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="taskuser", password="pass"
        )

        self.clinic = Clinic.objects.create(name="Clinic T")
        self.department = Department.objects.create(
            clinic=self.clinic,
            name="OT",
            is_active=True
        )

        self.employee = Employee.objects.create(
            user=self.user,
            clinic=self.clinic,
            dep=self.department,
            emp_type="Nurse",
            emp_name="Alice"
        )

        self.task_event = Task_Event.objects.create(
            name="Operation",
            dep=self.department
        )

    # -------------------------
    # CREATE
    # -------------------------
    def test_task_create_with_subtask_and_document(self):
        """TaskSerializer CREATE – success"""

        payload = {
            "task_event": self.task_event.id,
            "assignment": self.employee.id,
            "name": "Prepare Room",
            "description": "Sterilize OT",
            "due_date": timezone.now(),
            "status": STATUS_PENDING,
            "sub_tasks": [
                {
                    "name": "Clean floor",
                    "due_date": timezone.now(),
                    "status": STATUS_PENDING
                }
            ],
            "documents": [
                {
                    "document_name": "instructions.pdf",
                    "data": "filedata"
                }
            ]
        }

        serializer = TaskSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        task = serializer.save()

        self.assertEqual(Task.objects.count(), 1)
        self.assertEqual(task.subtask_set.count(), 1)
        self.assertEqual(task.document_set.count(), 1)

    # -------------------------
    # UPDATE
    # -------------------------
    def test_task_update_invalid_subtask_id_fails(self):
        """Updating subtask not belonging to task must fail"""

        task = Task.objects.create(
            task_event=self.task_event,
            assignment=self.employee,
            name="Main Task",
            description="Desc",
            due_date=timezone.now(),
            status=STATUS_PENDING
        )

        payload = {
            "name": "Updated",
            "sub_tasks": [
                {
                    "id": 999,  # ❌ invalid
                    "name": "Bad",
                    "due_date": timezone.now(),
                    "status": STATUS_PENDING
                }
            ]
        }

        serializer = TaskSerializer(
            instance=task,
            data=payload,
            partial=True
        )

        self.assertTrue(serializer.is_valid())

        with self.assertRaises(ValidationError):
            serializer.save()
