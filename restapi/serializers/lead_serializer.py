from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from restapi.utils.permissions import get_user_permissions, has_permission
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

    documents = serializers.SerializerMethodField()

    # 🔥 ADDED (Referral - SAFE)
    referral_source_id = serializers.IntegerField(source="referral_source.id", read_only=True)
    referral_source_name = serializers.CharField(source="referral_source.name", read_only=True)
    referral_source_type = serializers.CharField(source="referral_source.type", read_only=True)
    referral_clinic_name = serializers.CharField(
        source="referral_source.external_clinic.name",
        read_only=True
    )

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

            # 🔥 ADDED
            "referral_source_id",
            "referral_source_name",
            "referral_source_type",
            "referral_clinic_name",

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

    def to_representation(self, instance):
        data = super().to_representation(instance)

        request = self.context.get("request")
        if not request:
            return data

        user = request.user

        if user.profile.role.name.lower() == "super admin":
            return data

        if not has_permission(user, "lead", "leads", "view"):
            return {}

        allowed_fields = [
            "id",
            "full_name",
            "contact_no",
            "lead_status",
            "created_at"
        ]

        return {k: v for k, v in data.items() if k in allowed_fields}


# =====================================================
# Lead WRITE Serializer
# =====================================================

class LeadSerializer(serializers.ModelSerializer):

    clinic_id = serializers.IntegerField(write_only=True, required=False)
    department_id = serializers.IntegerField(write_only=True, required=False)

    assigned_to_id = serializers.IntegerField(required=False, allow_null=True)
    assigned_to_name = serializers.CharField(required=False, allow_null=True)

    personal_id = serializers.IntegerField(required=False, allow_null=True)
    personal_name = serializers.CharField(required=False, allow_null=True)

    campaign_id = serializers.UUIDField(required=False, allow_null=True)

    # 🔥 ADDED (Referral input - SAFE)
    referral_source_id = serializers.IntegerField(required=False, allow_null=True)

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
            "assigned_to_name",

            "personal_id",
            "personal_name",

            # 🔥 ADDED
            "referral_source_id",

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

            if "clinic_id" in attrs:
                if attrs["clinic_id"] != self.instance.clinic_id:
                    raise ValidationError({"clinic_id": "Cannot change clinic"})
                attrs.pop("clinic_id")

            if "department_id" in attrs:
                if attrs["department_id"] != self.instance.department_id:
                    raise ValidationError({"department_id": "Cannot change department"})
                attrs.pop("department_id")

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")

        # 🔥 ADDED (Referral handling)
        referral_source_id = validated_data.pop("referral_source_id", None)
        if referral_source_id:
            from restapi.models.referral import ReferralSource
            try:
                validated_data["referral_source"] = ReferralSource.objects.get(id=referral_source_id)
            except ReferralSource.DoesNotExist:
                raise ValidationError({"referral_source_id": "Invalid referral source"})

        if request and hasattr(request.user, "employee"):
            validated_data["created_by_id"] = request.user.employee.id
            validated_data["created_by_name"] = request.user.employee.emp_name

        return create_lead(validated_data)

    def update(self, instance, validated_data):
        request = self.context.get("request")

        # 🔥 ADDED (Referral handling)
        referral_source_id = validated_data.pop("referral_source_id", None)
        if referral_source_id is not None:
            from restapi.models.referral import ReferralSource
            try:
                instance.referral_source = ReferralSource.objects.get(id=referral_source_id)
            except ReferralSource.DoesNotExist:
                raise ValidationError({"referral_source_id": "Invalid referral source"})

        if request and hasattr(request.user, "employee"):
            validated_data["updated_by_id"] = request.user.employee.id
            validated_data["updated_by_name"] = request.user.employee.emp_name

        return update_lead(instance, validated_data)