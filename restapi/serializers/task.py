from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from restapi.models import Task, SubTask, Document, Task_Event, Employee
from restapi.services.task_service import (
    create_task,
    update_task,
    validate_task_activate,
    activate_task,
)


# =====================================================
# SubTask Serializer
# =====================================================
class SubTaskSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = SubTask
        fields = [
            "id",
            "due_date",
            "name",     # ✅ payload must send name
            "status",
        ]


# =====================================================
# Document Serializer
# =====================================================
class DocumentSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = Document
        fields = [
            "id",
            "document_name",
            "data",
        ]


# =====================================================
# Task WRITE Serializer
# =====================================================
class TaskSerializer(serializers.ModelSerializer):
    sub_tasks = SubTaskSerializer(many=True, required=False)
    documents = DocumentSerializer(many=True, required=False)

    task_event = serializers.PrimaryKeyRelatedField(
        queryset=Task_Event.objects.all()
    )

    assignment = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all()
    )

    class Meta:
        model = Task
        fields = [
            # ✅ FIXED
            "task_event",

            "assignment",
            "name",
            "due_date",
            "description",
            "status",

            # ⏱️ READ ONLY
            "timer_status",
            "total_tracked_sec",
            "timer_started_at",

            "sub_tasks",
            "documents",
        ]

        read_only_fields = [
            "timer_status",
            "total_tracked_sec",
            "timer_started_at",
        ]

    # =========================
    # CREATE
    # =========================
    def create(self, validated_data):
        return create_task(validated_data)

    # =========================
    # UPDATE (ID SAFE)
    # =========================
    def update(self, instance, validated_data):
        return update_task(instance, validated_data)


class SubTaskReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubTask
        fields = [
            "id",
            "assignment",
            "due_date",
            "name",
            "status",
            "created_at",
        ]


class DocumentReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id",
            "document_name",
            "created_at"
        ]


class TaskReadSerializer(serializers.ModelSerializer):
    sub_tasks = SubTaskReadSerializer(
        source="subtask_set",
        many=True
    )
    documents = DocumentReadSerializer(
        source="document_set",
        many=True
    )

    # ✅ Derived event (READ ONLY)
    event = serializers.IntegerField(
        source="task_event.event.id",
        read_only=True
    )

    task_event = serializers.IntegerField(
        source="task_event.id",
        read_only=True
    )

    class Meta:
        model = Task
        fields = [
            "id",

            # ✅ FIXED
            "event",
            "task_event",

            "assignment",
            "name",
            "description",
            "due_date",
            "status",

            # ⏱️ TASK TIMER FIELDS
            "timer_status",
            "total_tracked_sec",
            "timer_started_at",

            "sub_tasks",
            "documents",
            "created_at",
            "modified_at",
        ]


# =========================
# Task Activate Serializer
# =========================
class TaskActivateSerializer(serializers.Serializer):
    task_id = serializers.IntegerField()

    def validate(self, attrs):
        return validate_task_activate(attrs)

    def save(self):
        return activate_task(self.validated_data)
