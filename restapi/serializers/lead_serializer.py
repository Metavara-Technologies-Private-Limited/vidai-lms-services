# =====================================================
# Imports
# =====================================================
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from restapi.models import (
    Lead,
    Department,
    Employee,
    Campaign,
    LeadDocument,
    ReferralSource,
    ReferralDepartment,
    PipelineStage,
    Pipeline,
)

from restapi.services.lead_service import create_lead, update_lead


# =====================================================
# 🔥 CUSTOM FIELD (FINAL FIXED)
# =====================================================
class MultiFileField(serializers.ListField):
    child = serializers.FileField()

    def get_value(self, dictionary):
        # ✅ ALWAYS RETURN LIST (FIXED)
        if hasattr(dictionary, "getlist"):
            return dictionary.getlist(self.field_name) or []
        return dictionary.get(self.field_name) or []

    def to_internal_value(self, data):
        # ✅ HANDLE ALL EMPTY CASES (CRITICAL FIX)
        if not data or data in ["", None, "null", "undefined"]:
            return []

        # if single file comes instead of list
        if not isinstance(data, list):
            data = [data]

        return super().to_internal_value(data)

    def validate(self, files):
        # ✅ DOCUMENTS OPTIONAL
        if not files:
            return []

        allowed_extensions = [
            ".pdf", ".doc", ".docx",
            ".xls", ".xlsx",
            ".png", ".jpg", ".jpeg",
            ".txt", ".csv"
        ]

        max_file_size = 10 * 1024 * 1024  # 10MB

        for file in files:
            name = file.name.lower()

            if not any(name.endswith(ext) for ext in allowed_extensions):
                raise ValidationError(f"{file.name} is not a supported file type")

            if file.size > max_file_size:
                raise ValidationError(f"{file.name} exceeds 10MB limit")

        return files
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

    updated_by_id = serializers.IntegerField(read_only=True)
    updated_by_name = serializers.CharField(read_only=True)

    campaign_duration = serializers.SerializerMethodField()

    assigned_to_id = serializers.IntegerField(read_only=True)
    assigned_to_name = serializers.CharField(read_only=True)

    personal_id = serializers.IntegerField(read_only=True)
    personal_name = serializers.CharField(read_only=True)

    created_by_id = serializers.IntegerField(read_only=True)
    created_by_name = serializers.CharField(read_only=True)

    # REFERRAL
    referral_department_id = serializers.IntegerField(source="referral_department.id", read_only=True)
    referral_department_name = serializers.CharField(source="referral_department.name", read_only=True)

    referral_source_id = serializers.IntegerField(source="referral_source.id", read_only=True)
    referral_source_name = serializers.CharField(source="referral_source.name", read_only=True)

    referral_source_email = serializers.CharField(source="referral_source.email", read_only=True)
    referral_source_phone = serializers.CharField(source="referral_source.phone", read_only=True)

    # 🔥 CONVERSION TRACKING
    converted_at_stage_id = serializers.UUIDField(source="converted_at_stage.id", read_only=True)
    converted_at_stage_name = serializers.CharField(source="converted_at_stage.stage_name", read_only=True)

    # STAGE
    stage_id = serializers.UUIDField(source="stage.id", read_only=True)
    stage_name = serializers.CharField(source="stage.stage_name", read_only=True)

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

    campaign_id = serializers.UUIDField(required=False, allow_null=True)

    assigned_to_id = serializers.IntegerField(required=False, allow_null=True)
    assigned_to_name = serializers.CharField(required=False, allow_null=True)

    personal_id = serializers.IntegerField(required=False, allow_null=True)
    personal_name = serializers.CharField(required=False, allow_null=True)

    contact_no = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    referral_department_id = serializers.IntegerField(required=False, allow_null=True)
    referral_source_id = serializers.IntegerField(required=False, allow_null=True)
    referral_source = serializers.JSONField(required=False)

    pipeline_id = serializers.UUIDField(required=False, allow_null=True)
    stage_id = serializers.UUIDField(required=False, allow_null=True)

    documents = MultiFileField(write_only=True, required=False)

    contact_full_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    contact_designation = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    contact_phone = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_null=True)

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

            # CONTACT INFORMATION
            "contact_full_name",
            "contact_designation",
            "contact_phone",
            "contact_email",

            "partner_inquiry",
            "partner_full_name",
            "partner_age",
            "partner_gender",

            "source",
            "sub_source",

            # REFERRAL
            "referral_department_id",
            "referral_source_id",
            "referral_source",

            # PIPELINE + STAGE
            "pipeline_id",
            "stage_id",

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
    # 🔥 FIX 1: NORMALIZE STATUS
    # =====================================================
    def validate_lead_status(self, value):
        if value is None:
            return None

        value = str(value).strip().lower()

        if value == "":
            return None

        return value

    # =====================================================
    # PHONE VALIDATION
    # =====================================================
    def validate_contact_no(self, value):

        if value is None:
            return None

        value = str(value).strip()

        if value == "":
            return None

        if value in ["0", "00", "000", "0000000000"]:
            return None

        value = value.replace(" ", "")

        if value.startswith("+"):
            digits = value[1:]

            if not digits.isdigit():
                raise ValidationError("Invalid international phone number")

            if len(digits) < 7 or len(digits) > 15:
                raise ValidationError("Invalid international phone number")

            return value

        if value.startswith("+91"):
            value = value[3:]
        elif value.startswith("91") and len(value) == 12:
            value = value[2:]

        if not value.isdigit():
            raise ValidationError("Phone must contain digits only")

        if len(value) != 10:
            raise ValidationError("Phone must be 10 digits")

        invalid_numbers = {
            "1111111111","2222222222","3333333333",
            "4444444444","5555555555","6666666666",
            "7777777777","8888888888","9999999999",
            "1234567890","0123456789"
        }

        if value in invalid_numbers:
            raise ValidationError("Invalid phone number")

        return value

    # =====================================================
    # VALIDATION
    # =====================================================
    def validate(self, attrs):
        request = self.context.get("request")

        clinic_id = attrs.get("clinic_id") or request.headers.get("X-Clinic-Id")

        if not clinic_id:
            raise ValidationError({"clinic_id": "Clinic is required"})

        pipeline_id = attrs.get("pipeline_id")

        if pipeline_id:
            if not Pipeline.objects.filter(
                id=pipeline_id,
                clinic_id=clinic_id,
                is_deleted=False
            ).exists():
                raise ValidationError({"pipeline_id": "Invalid pipeline"})
        # ================= REFERRAL =================
        ref_dept_id = attrs.get("referral_department_id")
        ref_source_id = attrs.get("referral_source_id")

        referral_source_data = request.data.get("referral_source") if request else None

        if referral_source_data:
            if not referral_source_data.get("first_name"):
                raise ValidationError({"referral_source": "first_name required"})

        if ref_source_id and not ref_dept_id:
            raise ValidationError({
                "referral_department_id": "Required when referral_source is provided"
            })

        if ref_dept_id:
            if not ReferralDepartment.objects.filter(
                id=ref_dept_id,
                clinic_id=clinic_id,
                is_active=True
            ).exists():
                raise ValidationError({"referral_department_id": "Invalid referral department"})

        if ref_source_id:
            source = ReferralSource.objects.filter(
                id=ref_source_id,
                clinic_id=clinic_id
            ).first()

            if not source:
                raise ValidationError({"referral_source_id": "Invalid referral source"})

            if ref_dept_id and source.referral_department_id != ref_dept_id:
                raise ValidationError("Referral Source does not belong to selected Department")

        # ================= STAGE =================
        stage_id = attrs.get("stage_id")

        if stage_id:
            stage = PipelineStage.objects.filter(
                id=stage_id,
                is_active=True,
                is_deleted=False
            ).select_related("pipeline").first()

            if not stage:
                raise ValidationError({"stage_id": "Invalid stage"})

            if str(stage.pipeline.clinic_id) != str(clinic_id):
                raise ValidationError({"stage_id": "Invalid clinic stage"})

            if pipeline_id and str(stage.pipeline_id) != str(pipeline_id):
                raise ValidationError({"stage_id": "Stage not in selected pipeline"})

        return attrs

    # =====================================================
    # CREATE
    # =====================================================
    def create(self, validated_data):
        request = self.context.get("request")

        validated_data.pop("pipeline_id", None)

        # if validated_data.get("full_name"):
        #     validated_data["personal_name"] = validated_data["full_name"]

        return create_lead(validated_data, request=request)

    # =====================================================
    # UPDATE
    # =====================================================
    def update(self, instance, validated_data):
        request = self.context.get("request")

        validated_data.pop("pipeline_id", None)

        # if validated_data.get("full_name"):
        #     validated_data["personal_name"] = validated_data["full_name"]

        # =====================================================
        # 🔥 FIX 2: FORCE STATUS INTO SERVICE
        # =====================================================
        if request and "lead_status" in request.data:
            validated_data["lead_status"] = request.data.get("lead_status")

        return update_lead(instance, validated_data, request=request)