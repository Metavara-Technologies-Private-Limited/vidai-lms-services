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
from restapi.services.lead_service import create_lead, update_lead


# =====================================================
# 🔥 CUSTOM FIELD (UNCHANGED)
# =====================================================
class MultiFileField(serializers.ListField):
    child = serializers.FileField()

    def to_internal_value(self, data):
        if hasattr(data, "getlist"):
            data = data.getlist("documents")
        return super().to_internal_value(data)


# =====================================================
# Lead READ Serializer (ONLY ADDED FIELDS)
# =====================================================
class LeadReadSerializer(serializers.ModelSerializer):

    clinic_id = serializers.IntegerField(source="clinic.id", read_only=True)
    clinic_name = serializers.CharField(source="clinic.name", read_only=True)

    department_id = serializers.IntegerField(source="department.id", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

    campaign_id = serializers.UUIDField(source="campaign.id", read_only=True)
    campaign_name = serializers.CharField(source="campaign.campaign_name", read_only=True)

    campaign_duration = serializers.SerializerMethodField()

    assigned_to_id = serializers.IntegerField(read_only=True)
    assigned_to_name = serializers.CharField(read_only=True)

    personal_id = serializers.IntegerField(read_only=True)
    personal_name = serializers.CharField(read_only=True)

    created_by_id = serializers.IntegerField(read_only=True)
    created_by_name = serializers.CharField(read_only=True)

    # ✅ ONLY ADD THESE 3 LINES
    from restapi.serializers.referral_serializer import ReferralSourceSerializer
    referral_source = ReferralSourceSerializer(read_only=True)
    documents = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = "__all__"

    def get_campaign_duration(self, obj):
        campaign = obj.campaign
        if not campaign:
            return None

        if not campaign.start_date or not campaign.end_date:
            return None

        return f"{campaign.start_date.strftime('%d/%m/%Y')} - {campaign.end_date.strftime('%d/%m/%Y')}"

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
# Lead WRITE Serializer (ONLY ADDED FIELD)
# =====================================================
class LeadSerializer(serializers.ModelSerializer):

    clinic_id = serializers.IntegerField(write_only=True, required=False)
    department_id = serializers.IntegerField(write_only=True, required=False)

    # ✅ ONLY ADD THIS FIELD
    referral_source = serializers.IntegerField(required=False, allow_null=True)

    assigned_to_id = serializers.IntegerField(required=False, allow_null=True)
    assigned_to_name = serializers.CharField(required=False, allow_null=True)

    personal_id = serializers.IntegerField(required=False, allow_null=True)
    personal_name = serializers.CharField(required=False, allow_null=True)

    campaign_id = serializers.UUIDField(required=False, allow_null=True)

    documents = MultiFileField(write_only=True, required=False)

    is_active = serializers.BooleanField(required=False)

    class Meta:
        model = Lead
        fields = [
            "id",
            "clinic_id",
            "department_id",
            "campaign_id",

            # ✅ ONLY ADD HERE
            "referral_source",

            "assigned_to_id",
            "assigned_to_name",
            "personal_id",
            "personal_name",
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
    # VALIDATION (UNCHANGED)
    # =====================================================
    def validate(self, attrs):
        request = self.context.get("request")

        if self.instance is None:
            if "clinic_id" not in attrs:
                raise ValidationError({"clinic_id": "This field is required."})
            if "department_id" not in attrs:
                raise ValidationError({"department_id": "This field is required."})

        if self.instance is not None and request:
            payload_id = request.data.get("id")
            if payload_id and str(payload_id) != str(self.instance.id):
                raise ValidationError({"id": "Lead ID mismatch"})

        return attrs

    # =====================================================
    # CREATE (UNCHANGED)
    # =====================================================
    def create(self, validated_data):
        request = self.context.get("request")

        if request and hasattr(request.user, "employee"):
            validated_data["created_by_id"] = request.user.employee.id
            validated_data["created_by_name"] = request.user.employee.emp_name

        return create_lead(validated_data, request=request)

    # =====================================================
    # UPDATE (UNCHANGED)
    # =====================================================
    def update(self, instance, validated_data):
        request = self.context.get("request")

        if request and hasattr(request.user, "employee"):
            validated_data["updated_by_id"] = request.user.employee.id
            validated_data["updated_by_name"] = request.user.employee.emp_name

        return update_lead(instance, validated_data)