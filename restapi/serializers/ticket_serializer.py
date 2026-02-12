from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.utils import timezone

from restapi.models import Ticket, Document, TicketTimeline, Lab
from restapi.services.ticket_service import (
    create_ticket_service,
    update_ticket_service,
    create_lab_service,
    update_lab_service,
)

# ============================================================
# LAB READ SERIALIZER
# ============================================================
class LabReadSerializer(serializers.ModelSerializer):

    clinic_name = serializers.CharField(
        source="clinic.name",
        read_only=True
    )

    class Meta:
        model = Lab
        fields = "__all__"

# ============================================================
# LAB WRITE SERIALIZER
# ============================================================
class LabWriteSerializer(serializers.ModelSerializer):

    class Meta:
        model = Lab
        fields = [
            "name",
            
            "is_active",
        ]

    # --------------------------------------------------------
    # CREATE
    # --------------------------------------------------------
    def create(self, validated_data):
        return create_lab_service(validated_data)

    # --------------------------------------------------------
    # UPDATE
    # --------------------------------------------------------
    def update(self, instance, validated_data):
        return update_lab_service(instance, validated_data)

# ============================================================
# DOCUMENT SERIALIZER
# ============================================================
class TicketDocumentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Document
        fields = ["id", "file", "uploaded_at"]
        read_only_fields = ["uploaded_at"]


# ============================================================
# TICKET TIMELINE SERIALIZER
# ============================================================
class TicketTimelineSerializer(serializers.ModelSerializer):

    done_by_name = serializers.CharField(
        source="done_by.name",
        read_only=True
    )

    class Meta:
        model = TicketTimeline
        fields = [
            "id",
            "action",
            "done_by",
            "done_by_name",
            "created_at",
        ]


# ============================================================
# TICKET LIST SERIALIZER (For Table View)
# ============================================================
class TicketListSerializer(serializers.ModelSerializer):

    lab_name = serializers.CharField(source="lab.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    assigned_to_name = serializers.CharField(source="assigned_to.name", read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "ticket_no",
            "lab",
            "lab_name",
            "subject",
            "created_at",
            "due_date",
            "requested_by",
            "department",
            "department_name",
            "priority",
            "assigned_to",
            "assigned_to_name",
            "status",
        ]


# ============================================================
# TICKET DETAIL SERIALIZER (Full View)
# ============================================================
class TicketDetailSerializer(serializers.ModelSerializer):

    documents = TicketDocumentSerializer(many=True, read_only=True)
    timeline = TicketTimelineSerializer(many=True, read_only=True)

    lab_name = serializers.CharField(source="lab.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    assigned_to_name = serializers.CharField(source="assigned_to.name", read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "ticket_no",
            "subject",
            "description",
            "lab",
            "lab_name",
            "department",
            "department_name",
            "requested_by",
            "assigned_to",
            "assigned_to_name",
            "priority",
            "status",
            "due_date",
            "created_at",
            "updated_at",
            "resolved_at",
            "closed_at",
            "is_deleted",
            "deleted_at",
            "documents",
            "timeline",
        ]



# ============================================================
# TICKET WRITE SERIALIZER (Create / Update)
# ============================================================
class TicketWriteSerializer(serializers.ModelSerializer):

    documents = TicketDocumentSerializer(many=True, required=False)

    class Meta:
        model = Ticket
        fields = [
            "subject",
            "description",
            "lab",
            "department",
            "requested_by",
            "assigned_to",
            "priority",
            "status",
            "due_date",
            "documents",
        ]

    # --------------------------------------------------------
    # FIELD VALIDATION
    # Ensure due date is not in the past
    # --------------------------------------------------------
    def validate_due_date(self, value):
        if value and value < timezone.now().date():
            raise ValidationError(
                "Due date cannot be set in the past."
            )
        return value

    # --------------------------------------------------------
    # OBJECT VALIDATION
    # Ensure assigned employee belongs to selected department
    # --------------------------------------------------------
    def validate(self, validated_data):

        assigned_employee = validated_data.get("assigned_to")
        selected_department = validated_data.get("department")

        # Only validate if both fields are present
        if assigned_employee and selected_department:

            # 🔥 FIXED HERE (use dep, not department)
            if assigned_employee.dep != selected_department:
                raise ValidationError(
                    "Assigned employee does not belong to the selected department."
                )

        return validated_data

    # --------------------------------------------------------
    # CREATE
    # --------------------------------------------------------
    def create(self, validated_data):
        return create_ticket_service(validated_data)

    # --------------------------------------------------------
    # UPDATE
    # --------------------------------------------------------
    def update(self, instance, validated_data):
        return update_ticket_service(instance, validated_data)
