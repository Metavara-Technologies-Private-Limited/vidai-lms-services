# =====================================================
# Imports
# =====================================================
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
import json

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
    LeadFormField,
    LeadCustomFieldValue,
)

from restapi.services.lead_service import create_lead, update_lead
from django.utils import timezone


# =====================================================
# 🔥 CUSTOM FIELD (FINAL FIX)
# =====================================================
class MultiFileField(serializers.ListField):
    child = serializers.FileField()

    def get_value(self, dictionary):
        if hasattr(dictionary, "getlist"):
            files = dictionary.getlist(self.field_name)
            return files if files else []   # ✅ always list
        return dictionary.get(self.field_name, [])

    def to_internal_value(self, data):
        # ✅ HANDLE ALL BAD INPUT TYPES
        if data in [None, "", {}, "null"]:
            return []

        if not isinstance(data, list):
            return []

        return super().to_internal_value(data)

    def validate(self, files):
        # ✅ OPTIONAL FIELD
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
            if not hasattr(file, "name"):
                continue

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
    treatment_interest = serializers.SerializerMethodField()

    documents = serializers.SerializerMethodField()
    custom_field_values = serializers.SerializerMethodField()
    quality = serializers.SerializerMethodField()
    last_interaction_at = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = "__all__"

    def get_campaign_duration(self, obj):
        campaign = obj.campaign
        if not campaign or not campaign.start_date or not campaign.end_date:
            return None
        return f"{campaign.start_date.strftime('%d/%m/%Y')} - {campaign.end_date.strftime('%d/%m/%Y')}"

    def get_documents(self, obj):
        # =====================================================
        # ✅ OPTIMIZATION: documents already prefetched from view,
        #    so this accesses in-memory data without additional DB queries
        # =====================================================
        return [
            {
                "id": doc.id,
                "file": doc.file.url if doc.file else None,
                "uploaded_at": doc.uploaded_at,
            }
            for doc in obj.documents.all()
        ]

    def get_treatment_interest(self, obj):
        # =====================================================
        # ✅ OPTIMIZATION: treatment_interest already prefetched from view,
        #    so this accesses in-memory data without additional DB queries
        # =====================================================
        return [
            {
                "id": interest.id,
                "name": interest.name
            }
            for interest in obj.treatment_interest.all()
        ]

    def get_custom_field_values(self, obj):
        values = getattr(obj, "custom_field_values", None)
        if values is None:
            return []

        return [
            {
                "field_key": item.field.field_key,
                "field_label": item.field.field_label,
                "field_type": item.field.field_type,
                "value": item.value,
            }
            for item in values.select_related("field").filter(field__is_active=True).order_by("field__sort_order", "field__field_label")
        ]

    # def get_last_interaction_at(self, obj):

    #     latest_call = obj.twilio_calls.filter(
    #         status__in=["completed", "answered", "in-progress"]
    #     ).aggregate(
    #         latest=Max("created_at")
    #     )["latest"]

    #     latest_sms = obj.twilio_messages.filter(
    #         status__in=[
    #             "queued",
    #             "queued_via_zapier",
    #             "sent",
    #             "delivered",
    #         ]
    #     ).aggregate(
    #         latest=Max("created_at")
    #     )["latest"]

    #     latest_email = obj.emails.filter(
    #         status="SENT",
    #         sent_at__isnull=False
    #     ).aggregate(
    #         latest=Max("sent_at")
    #     )["latest"]

    #     appointment_datetime = None

    #     if obj.book_appointment and obj.appointment_date:
    #         appointment_datetime = timezone.datetime.combine(
    #             obj.appointment_date,
    #             timezone.datetime.min.time(),
    #             tzinfo=timezone.get_current_timezone()
    #         )

    #     latest_dates = [
    #         latest_call,
    #         latest_sms,
    #         latest_email,
    #         appointment_datetime,
    #     ]

    #     valid_dates = [d for d in latest_dates if d]

    #     # ✅ FALLBACK TO LEAD CREATION
    #     if not valid_dates:
    #         return obj.created_at

    #     return max(valid_dates)
    def get_last_interaction_at(self, obj):
        return getattr(
            obj,
            "last_interaction_at_db",
            obj.created_at
        )

    def get_quality(self, obj):

        last_interaction = self.get_last_interaction_at(obj)

        if not last_interaction:
            return "Cold"

        diff_days = (
            timezone.now() - last_interaction
        ).days

        if diff_days <= 7:
            return "Hot"

        if diff_days <= 30:
            return "Warm"

        return "Cold"


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
        # ✅ INTEREST FIELD
    treatment_interest = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
)

    documents = MultiFileField(write_only=True, required=False)

    contact_full_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    contact_designation = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    contact_phone = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_null=True)

    # ── NEW: task / action status ─────────────────────────────────────────────
    action_status = serializers.ChoiceField(
        choices=["to_do", "in_progress", "completed"],
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    custom_field_values = serializers.JSONField(required=False)

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

            # ── NEW ──────────────────────────────────────────────────────────
            "action_status",
            "custom_field_values",

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
    # 🔥 FIX 1: NORMALIZE LEAD STATUS
    # =====================================================
    def validate_lead_status(self, value):
        if value is None:
            return None

        value = str(value).strip().lower()

        if value == "":
            return None

        return value

    # =====================================================
    # 🔥 NEW: NORMALIZE ACTION STATUS
    # Empty string → None so the DB stores NULL, not "".
    # =====================================================
    def validate_action_status(self, value):
        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip().lower()

        if value == "":
            return None

        allowed = {"to_do", "in_progress", "completed"}
        if value not in allowed:
            raise serializers.ValidationError(
                f"Invalid action_status '{value}'. Must be one of: {', '.join(sorted(allowed))}"
            )

        return value

    def validate_custom_field_values(self, value):
        if value in (None, "", "null"):
            return {}
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError("Invalid custom field values")
        if not isinstance(value, dict):
            raise serializers.ValidationError("Expected an object of field_key/value pairs")
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

        if not (7 <= len(value) <= 15):
            raise ValidationError("Phone must be between 7 and 15 digits")

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

        clinic_id = attrs.get("clinic_id")

        if not clinic_id and request:
            clinic_id = (
                request.query_params.get("clinic_id")
                or request.data.get("clinic_id")
            )

        if not clinic_id:
            raise ValidationError({
                "clinic_id": "Clinic is required"
            })

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
        # ================= INTEREST FIX =================
        treatment_interest = attrs.get("treatment_interest")

        if treatment_interest in [None, "", "null"]:
            attrs["treatment_interest"] = []

        return attrs

        return attrs

    # =====================================================
    # CREATE
    # =====================================================
    def create(self, validated_data):
        request = self.context.get("request")

        validated_data.pop("pipeline_id", None)

        return create_lead(validated_data, request=request)

    # =====================================================
    # UPDATE
    # =====================================================
    def update(self, instance, validated_data):
        request = self.context.get("request")

        validated_data.pop("pipeline_id", None)

        # =====================================================
        # 🔥 FIX 2: FORCE STATUS INTO SERVICE
        # =====================================================
        if request and "lead_status" in request.data:
            validated_data["lead_status"] = request.data.get("lead_status")

        # ── Preserve explicit action_status from request data ─────────────────
        # The serializer field already validates it; this ensures an explicit
        # null/empty from the request correctly clears the field on update.
        if request and "action_status" in request.data:
            raw = request.data.get("action_status")
            if raw in (None, "", "null"):
                validated_data["action_status"] = None
            else:
                # Already validated + normalized by validate_action_status()
                validated_data.setdefault("action_status", raw)

        return update_lead(instance, validated_data, request=request)
