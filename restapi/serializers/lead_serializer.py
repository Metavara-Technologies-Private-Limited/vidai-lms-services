from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from restapi.models import (
    Lead,
    Clinic,
    Department,
    Employee,
    Campaign,
    LeadDocument,
    ReferralSource,
    ReferralDepartment,
)
from restapi.services.lead_service import create_lead, update_lead


# =====================================================
# 🔥 CUSTOM FIELD
# =====================================================
class MultiFileField(serializers.ListField):
    child = serializers.FileField()

    def to_internal_value(self, data):
        if hasattr(data, "getlist"):
            data = data.getlist("documents")
        return super().to_internal_value(data)


# =====================================================
# READ SERIALIZER
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

    # 🔥 REFERRAL DISPLAY
    referral_department_id = serializers.IntegerField(source="referral_department.id", read_only=True)
    referral_department_name = serializers.CharField(source="referral_department.name", read_only=True)

    referral_source_id = serializers.IntegerField(source="referral_source.id", read_only=True)
    referral_source_name = serializers.CharField(source="referral_source.name", read_only=True)

    documents = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = "__all__"

    def get_campaign_duration(self, obj):
        campaign = obj.campaign
        if not campaign or not campaign.start_date or not campaign.end_date:
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
# WRITE SERIALIZER
# =====================================================
class LeadSerializer(serializers.ModelSerializer):

    clinic_id = serializers.IntegerField(write_only=True, required=False)
    department_id = serializers.IntegerField(write_only=True, required=False)

    assigned_to_id = serializers.IntegerField(required=False, allow_null=True)
    assigned_to_name = serializers.CharField(required=False, allow_null=True)

    personal_id = serializers.IntegerField(required=False, allow_null=True)
    personal_name = serializers.CharField(required=False, allow_null=True)

    campaign_id = serializers.UUIDField(required=False, allow_null=True)

    # 🔥 REFERRAL
    referral_department_id = serializers.IntegerField(required=False, allow_null=True)
    referral_source_id = serializers.IntegerField(required=False, allow_null=True)

    documents = MultiFileField(write_only=True, required=False)
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

            # 🔥 REFERRAL
            "referral_department_id",
            "referral_source_id",

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

        # ================= BASIC =================
        if self.instance is None:
            if "clinic_id" not in attrs:
                raise ValidationError({"clinic_id": "This field is required."})
            if "department_id" not in attrs:
                raise ValidationError({"department_id": "This field is required."})

        if self.instance is not None and request:
            payload_id = request.data.get("id")
            if payload_id and str(payload_id) != str(self.instance.id):
                raise ValidationError({"id": "Lead ID mismatch"})

        # ================= REFERRAL =================
        ref_dept_id = attrs.get("referral_department_id")
        ref_source_id = attrs.get("referral_source_id")

        clinic_id = (
            attrs.get("clinic_id")
            or request.headers.get("X-Clinic-Id")
            or request.data.get("clinic_id")
        )

        if ref_source_id and not ref_dept_id:
            raise ValidationError({
                "referral_department_id": "Required when referral_source is provided"
            })

        if ref_dept_id:
            dept = ReferralDepartment.objects.filter(
                id=ref_dept_id,
                clinic_id=clinic_id,
                is_active=True
            ).first()

            if not dept:
                raise ValidationError({"referral_department_id": "Invalid referral department"})

        if ref_source_id:
            source = ReferralSource.objects.filter(
                id=ref_source_id,
                clinic_id=clinic_id
            ).first()

            if not source:
                raise ValidationError({"referral_source_id": "Invalid referral source"})

            if ref_dept_id and source.referral_department_id != ref_dept_id:
                raise ValidationError(
                    "Referral Source does not belong to selected Department"
                )

        return attrs

    # =====================================================
    # CREATE
    # =====================================================
    def create(self, validated_data):
        request = self.context.get("request")

        if request and hasattr(request.user, "employee"):
            validated_data["created_by_id"] = request.user.employee.id
            validated_data["created_by_name"] = request.user.employee.emp_name

        return create_lead(validated_data, request=request)

    # =====================================================
    # UPDATE
    # =====================================================
    def update(self, instance, validated_data):
        request = self.context.get("request")

        if request and hasattr(request.user, "employee"):
            validated_data["updated_by_id"] = request.user.employee.id
            validated_data["updated_by_name"] = request.user.employee.emp_name

        return update_lead(instance, validated_data)