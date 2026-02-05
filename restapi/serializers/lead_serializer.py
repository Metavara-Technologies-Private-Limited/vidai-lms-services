from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from restapi.models import (
    Lead,
    Clinic,
    Department,
    Employee,
    Campaign,
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

    assigned_to_id = serializers.IntegerField(source="assigned_to.id", read_only=True)
    assigned_to_name = serializers.CharField(source="assigned_to.emp_name", read_only=True)

    personal_id = serializers.IntegerField(source="personal.id", read_only=True)
    personal_name = serializers.CharField(source="personal.emp_name", read_only=True)

    class Meta:
        model = Lead
        fields = [
            "id",

            # clinic
            "clinic_id",
            "clinic_name",

            # department
            "department_id",
            "department_name",

            # campaign
            "campaign_id",
            "campaign_name",

            # employee mappings
            "assigned_to_id",
            "assigned_to_name",
            "personal_id",
            "personal_name",

            # lead data
            "full_name",
            "age",
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
            "next_action_description",
            "treatment_interest",
            "document",
            "book_appointment",
            "appointment_date",
            "slot",
            "remark",
            "created_at",
            "modified_at",
            "is_active"
        ]


# =====================================================
# Lead WRITE Serializer (POST + PUT)
# =====================================================
class LeadSerializer(serializers.ModelSerializer):
    clinic_id = serializers.IntegerField(write_only=True, required=False)
    department_id = serializers.IntegerField(write_only=True, required=False)
    assigned_to_id = serializers.IntegerField(required=False, allow_null=True)
    personal_id = serializers.IntegerField(required=False, allow_null=True)
    campaign_id = serializers.UUIDField(required=False, allow_null=True)
    document = serializers.FileField(required=False, allow_null=True)
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
            "next_action_description",
            "treatment_interest",
            "document",
            "book_appointment",
            "appointment_date",
            "slot",
            "remark",
            "is_active",
        ]

    # -------------------------
    # GLOBAL VALIDATION
    # -------------------------
    def validate(self, attrs):
        # CREATE → require clinic & department
        if self.instance is None:
            if "clinic_id" not in attrs:
                raise ValidationError({"clinic_id": "This field is required."})
            if "department_id" not in attrs:
                raise ValidationError({"department_id": "This field is required."})

        # UPDATE → allow SAME IDs, block CHANGES
        if self.instance is not None:
            if "clinic_id" in attrs:
                if attrs["clinic_id"] != self.instance.clinic_id:
                    raise ValidationError({"clinic_id": "clinic_id cannot be changed"})
                attrs.pop("clinic_id")

            if "department_id" in attrs:
                if attrs["department_id"] != self.instance.department_id:
                    raise ValidationError({"department_id": "department_id cannot be changed"})
                attrs.pop("department_id")

        return attrs

    def create(self, validated_data):
        return create_lead(validated_data)

    def update(self, instance, validated_data):
        return update_lead(instance, validated_data)