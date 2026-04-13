from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from restapi.utils.permissions import get_user_permissions, has_permission
from restapi.models import Ticket, Document, TicketTimeline, Lab, TicketReply, Employee
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

    assigned_to_name = serializers.CharField(read_only=True)

    class Meta:
        model = Lab
        fields = "__all__"

    # =====================================================
    # RBAC FILTERING
    # =====================================================
    def to_representation(self, instance):
        data = super().to_representation(instance)

        request = self.context.get("request")
        if not request:
            return data

        user = request.user

        # ✅ SUPER ADMIN → FULL ACCESS
        if user.profile.role.name.lower() == "super admin":
            return data

        # ❌ NO PERMISSION → EMPTY
        if not has_permission(user, "lab", "labs", "view"):
            return {}

        # 🔥 FIELD FILTERING
        allowed_fields = [
            "id",
            "name",
            "clinic_name",
            "department_name",
            "assigned_to_name",
            "is_active"
        ]

        return {k: v for k, v in data.items() if k in allowed_fields}

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

    file = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = ["id", "file", "uploaded_at"]

    def get_file(self, obj):
        request = self.context.get("request")
        if obj.file:
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


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
            "done_by_id",
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
    assigned_to = serializers.IntegerField(
        source="assigned_to_id",
        required=False,
        allow_null=True,
        write_only=True,
    )
    assigned_to_id = serializers.IntegerField(read_only=True)
    assigned_to_name = serializers.CharField(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "subject",
            "description",
            "lab",
            "department",
            "requested_by",
            "assigned_to",
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

    def validate(self, validated_data):
        assigned_employee_id = validated_data.get("assigned_to_id")
        selected_department = validated_data.get("department")

        if not assigned_employee_id:
            validated_data["assigned_to_name"] = None
            return validated_data

        try:
            assigned_employee = Employee.objects.select_related("dep").get(
                id=assigned_employee_id,
            )
        except Employee.DoesNotExist:
            fallback_name_raw = self.initial_data.get("assigned_to_name")
            fallback_name = (
                str(fallback_name_raw).strip()
                if fallback_name_raw is not None
                else ""
            )
            validated_data["assigned_to_name"] = fallback_name or f"User {assigned_employee_id}"
            return validated_data

        if selected_department and assigned_employee.dep_id != selected_department.id:
            fallback_name_raw = self.initial_data.get("assigned_to_name")
            fallback_name = (
                str(fallback_name_raw).strip()
                if fallback_name_raw is not None
                else ""
            )
            validated_data["assigned_to_name"] = fallback_name or assigned_employee.emp_name
            return validated_data

        validated_data["assigned_to_name"] = assigned_employee.emp_name
        return validated_data

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