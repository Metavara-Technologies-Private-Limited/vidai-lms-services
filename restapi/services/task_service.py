from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from restapi.models import Task, SubTask, Document


# =========================
# CREATE
# =========================
@transaction.atomic
def create_task(validated_data):
    sub_tasks_data = validated_data.pop("sub_tasks", [])
    documents_data = validated_data.pop("documents", [])

    task_instance = Task.objects.create(**validated_data)

    # Create sub-tasks
    for sub_task_data in sub_tasks_data:
        SubTask.objects.create(
            task=task_instance,
            assignment=task_instance.assignment,
            **sub_task_data
        )

    # Create documents
    for document_data in documents_data:
        Document.objects.create(
            task=task_instance,
            **document_data
        )

    return task_instance


# =========================
# UPDATE (ID SAFE)
# =========================
@transaction.atomic
def update_task(instance, validated_data):
    validated_data.pop("assignment", None)
    validated_data.pop("task_event", None)  # ❗ optional: prevent reassignment

    sub_tasks_data = validated_data.pop("sub_tasks", [])
    documents_data = validated_data.pop("documents", [])

    # ---- update task fields ----
    for field_name, field_value in validated_data.items():
        setattr(instance, field_name, field_value)
    instance.save()

    # =========================
    # SUB TASKS
    # =========================
    existing_subtasks = {
        subtask.id: subtask
        for subtask in instance.subtask_set.all()
    }

    received_subtask_ids = []

    for sub_task_data in sub_tasks_data:
        sub_task_id = sub_task_data.get("id")

        if sub_task_id:
            sub_task_instance = existing_subtasks.get(sub_task_id)
            if not sub_task_instance:
                raise serializers.ValidationError({
                    "sub_tasks": f"SubTask {sub_task_id} does not belong to this task"
                })

            sub_task_instance.due_date = sub_task_data["due_date"]
            sub_task_instance.name = sub_task_data["name"]
            sub_task_instance.status = sub_task_data.get(
                "status",
                sub_task_instance.status
            )
            sub_task_instance.save()

            received_subtask_ids.append(sub_task_id)
        else:
            new_subtask = SubTask.objects.create(
                task=instance,
                assignment=instance.assignment,
                **sub_task_data
            )
            received_subtask_ids.append(new_subtask.id)

    for subtask_id, subtask in existing_subtasks.items():
        if subtask_id not in received_subtask_ids:
            subtask.delete()

    # =========================
    # DOCUMENTS
    # =========================
    existing_documents = {
        doc.id: doc
        for doc in instance.document_set.all()
    }

    received_document_ids = []

    for document_data in documents_data:
        document_id = document_data.get("id")

        if document_id:
            document_instance = existing_documents.get(document_id)
            if not document_instance:
                raise serializers.ValidationError({
                    "documents": f"Document {document_id} does not belong to this task"
                })

            document_instance.document_name = document_data.get(
                "document_name",
                document_instance.document_name
            )

            if "data" in document_data:
                document_instance.data = document_data["data"]

            document_instance.save()
            received_document_ids.append(document_id)
        else:
            new_document = Document.objects.create(
                task=instance,
                **document_data
            )
            received_document_ids.append(new_document.id)

    for doc_id, document in existing_documents.items():
        if doc_id not in received_document_ids:
            document.delete()

    return instance


# =========================
# Task Activate
# =========================
def validate_task_activate(attrs):
    try:
        task = Task.objects.get(id=attrs["task_id"])
    except Task.DoesNotExist:
        raise ValidationError("Invalid task id")

    attrs["task"] = task
    return attrs


def activate_task(validated_data):
    task = validated_data["task"]

    # assuming inactive task uses status
    task.status = "active"
    task.save(update_fields=["status"])
    return task
