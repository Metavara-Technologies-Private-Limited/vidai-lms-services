from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from restapi.models import (
    Lead,
    Clinic,
    Department,
    Employee,
    Campaign,
    LeadDocument,
)

from restapi.services.lead_service import (
    create_lead,
    update_lead,
)


# =====================================================
# Lead READ Serializer
# =====================================================

class LeadReadSerializer(serializers.ModelSerializer):

    # -------------------------
    # Existing Mappings
    # -------------------------
    clinic_id = serializers.IntegerField(source="clinic.id", read_only=True)
    clinic_name = serializers.CharField(source="clinic.name", read_only=True)

    department_id = serializers.IntegerField(source="department.id", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

    campaign_id = serializers.UUIDField(source="campaign.id", read_only=True)
    campaign_name = serializers.CharField(source="campaign.campaign_name", read_only=True)
    # ✅ ADDED: Computed from campaign.start_date and campaign.end_date
    # Returns a human-readable string e.g. "18 days" or None if no campaign
    campaign_duration = serializers.SerializerMethodField()

    assigned_to_id = serializers.IntegerField(source="assigned_to.id", read_only=True)
    assigned_to_name = serializers.CharField(source="assigned_to.emp_name", read_only=True)

    personal_id = serializers.IntegerField(source="personal.id", read_only=True)
    personal_name = serializers.CharField(source="personal.emp_name", read_only=True)

    created_by_id = serializers.IntegerField(source="created_by.id", read_only=True)
    created_by_name = serializers.CharField(source="created_by.emp_name", read_only=True)

    documents = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            "id",

            "clinic_id", "clinic_name",
            "department_id", "department_name",
            "campaign_id", "campaign_name", "campaign_duration",
            "assigned_to_id", "assigned_to_name",
            "personal_id", "personal_name",

            "created_by_id",
            "created_by_name",

            "full_name",
            "age",
            "gender",
            "marital_status",
            "email",
            "contact_no",
            "language_preference",
            "location",
            "address",
            "partner_inquiry",
            "partner_full_name",
            "partner_age",
            "partner_gender",
            "source",
            "sub_source",
            "lead_status",
            "next_action_status",
            "next_action_type",
            "next_action_description",
            "treatment_interest",
            "book_appointment",
            "appointment_date",
            "slot",
            "remark",

            "documents",

            "created_at",
            "modified_at",
            "is_active",
            "converted_at",
        ]

    def get_campaign_duration(self, obj):
        """Return campaign date range as 'DD/MM/YYYY - DD/MM/YYYY'."""
        campaign = obj.campaign
        if not campaign:
            return None
        start = campaign.start_date
        end = campaign.end_date
        if not start or not end:
            return None
        return f"{start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}"

    def get_documents(self, obj):
        return [
            {
                "id": doc.id,
                "file": doc.file.url if doc.file else None,
                "uploaded_at": doc.uploaded_at,
            }
            for doc in obj.documents.all()
        ]


# =====================================================
# Lead WRITE Serializer
# =====================================================

class LeadSerializer(serializers.ModelSerializer):

    clinic_id = serializers.IntegerField(write_only=True, required=False)
    department_id = serializers.IntegerField(write_only=True, required=False)
    assigned_to_id = serializers.IntegerField(required=False, allow_null=True)
    personal_id = serializers.IntegerField(required=False, allow_null=True)
    campaign_id = serializers.UUIDField(required=False, allow_null=True)

    documents = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False
    )

    is_active = serializers.BooleanField(required=False)

    class Meta:
        model = Lead
        fields = [
            "id",
            "clinic_id",
            "department_id",
            "campaign_id",
            "assigned_to_id",
            "personal_id",

            "full_name",
            "age",
            "gender",
            "marital_status",
            "email",
            "contact_no",
            "language_preference",
            "location",
            "address",
            "partner_inquiry",
            "partner_full_name",
            "partner_age",
            "partner_gender",
            "source",
            "sub_source",
            "lead_status",
            "next_action_status",
            "next_action_type",
            "next_action_description",
            "treatment_interest",
            "book_appointment",
            "appointment_date",
            "slot",
            "remark",
            "documents",
            "is_active",
        ]

        read_only_fields = ("id",)

    # =====================================================
    # VALIDATION
    # =====================================================
    def validate(self, attrs):
        request = self.context.get("request")

        # CREATE → require clinic & department
        if self.instance is None:
            if "clinic_id" not in attrs:
                raise ValidationError({"clinic_id": "This field is required."})
            if "department_id" not in attrs:
                raise ValidationError({"department_id": "This field is required."})

        # UPDATE → prevent clinic/department change
        if self.instance is not None and request:
            payload_id = request.data.get("id")
            if payload_id and str(payload_id) != str(self.instance.id):
                raise ValidationError({"id": "Lead ID mismatch"})

            if "clinic_id" in attrs:
                if attrs["clinic_id"] != self.instance.clinic_id:
                    raise ValidationError({"clinic_id": "Cannot change clinic"})
                attrs.pop("clinic_id")

            if "department_id" in attrs:
                if attrs["department_id"] != self.instance.department_id:
                    raise ValidationError({"department_id": "Cannot change department"})
                attrs.pop("department_id")

        return attrs

    # =====================================================
    # CREATE
    # =====================================================
    def create(self, validated_data):
        request = self.context.get("request")
        if request and hasattr(request.user, "employee"):
            validated_data["created_by"] = request.user.employee

        return create_lead(validated_data)

    # =====================================================
    # UPDATE
    # =====================================================
    def update(self, instance, validated_data):
        return update_lead(instance, validated_data)