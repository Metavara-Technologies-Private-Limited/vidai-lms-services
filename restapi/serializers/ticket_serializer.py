from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.utils import timezone

from restapi.models import Ticket, Document, TicketTimeline, Lab, TicketReply
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

    department_name = serializers.CharField(
        source="department.name",
        read_only=True
    )

    # ✅ FIXED
    assigned_to_name = serializers.CharField(read_only=True)

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
            "clinic",
            "department",
            "assigned_to",
            "is_active",
        ]

    def create(self, validated_data):
        return create_lab_service(validated_data)

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

    # ✅ FIXED
    done_by_name = serializers.CharField(read_only=True)

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
# TICKET LIST SERIALIZER
# ============================================================
class TicketListSerializer(serializers.ModelSerializer):

    lab_name = serializers.CharField(source="lab.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

    # ✅ FIXED
    assigned_to_id = serializers.IntegerField(read_only=True)
    assigned_to_name = serializers.CharField(read_only=True)

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
            "assigned_to_id",
            "assigned_to_name",
            "status",
        ]


# ============================================================
# TICKET DETAIL SERIALIZER
# ============================================================
class TicketDetailSerializer(serializers.ModelSerializer):

    documents = TicketDocumentSerializer(many=True, read_only=True)
    timeline = TicketTimelineSerializer(many=True, read_only=True)

    lab_name = serializers.CharField(source="lab.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

    # ✅ FIXED
    assigned_to_id = serializers.IntegerField(read_only=True)
    assigned_to_name = serializers.CharField(read_only=True)

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
            "assigned_to_id",
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
# TICKET WRITE SERIALIZER
# ============================================================
class TicketWriteSerializer(serializers.ModelSerializer):

    documents = TicketDocumentSerializer(many=True, required=False)

    # ✅ NEW FIELDS
    assigned_to_id = serializers.IntegerField(required=False, allow_null=True)
    assigned_to_name = serializers.CharField(required=False, allow_null=True)

    class Meta:
        model = Ticket
        fields = [
            "subject",
            "description",
            "lab",
            "department",
            "requested_by",
            "assigned_to_id",
            "assigned_to_name",
            "priority",
            "status",
            "due_date",
            "documents",
        ]

    def validate_due_date(self, value):
        if value and value < timezone.now().date():
            raise ValidationError("Due date cannot be set in the past.")
        return value

    # ❌ REMOVED FK VALIDATION

    def create(self, validated_data):
        return create_ticket_service(validated_data)

    def update(self, instance, validated_data):
        return update_ticket_service(instance, validated_data)


# ============================================================
# TICKET REPLY SERIALIZER
# ============================================================
class TicketReplySerializer(serializers.ModelSerializer):

    # ✅ FIXED
    sent_by_name = serializers.CharField(read_only=True)

    class Meta:
        model = TicketReply
        fields = [
            "id",
            "ticket",
            "subject",
            "message",
            "to_emails",
            "cc_emails",
            "bcc_emails",
            "sent_by",
            "sent_by_name",
            "status",
            "failed_reason",
            "created_at",
        ]
        read_only_fields = ["id", "status", "failed_reason", "created_at"]


class TicketReplyWriteSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=255)
    message = serializers.CharField()
    to = serializers.ListField(child=serializers.EmailField(), min_length=1)
    cc = serializers.ListField(child=serializers.EmailField(), required=False, default=list)
    bcc = serializers.ListField(child=serializers.EmailField(), required=False, default=list)
    sent_by = serializers.IntegerField(required=False, allow_null=True)