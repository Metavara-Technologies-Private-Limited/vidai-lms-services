from rest_framework import serializers
from restapi.models import (
    Pipeline,
    PipelineStage,
    StageRule,
    StageField,
    LeadFormField,
)
from restapi.utils.permissions import get_user_permissions, has_permission
from rest_framework.exceptions import ValidationError

from restapi.services.pipeline_service import (
    create_pipeline,
    update_pipeline,
)

# =====================================================
# Stage Rule READ
# =====================================================
class StageRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = StageRule
        fields = [
            "id",
            "action_type",
            "custom_label",
            "is_enabled",
            "is_required",
            "auto_move",
            "allow_manual_move",
        ]


# =====================================================
# Stage Field READ
# =====================================================
class StageFieldSerializer(serializers.ModelSerializer):
    field_name = serializers.SerializerMethodField()
    field_type = serializers.SerializerMethodField()

    class Meta:
        model = StageField
        fields = [
            "id",
            "field_key",
            "field_name",
            "field_type",
            "is_mandatory",
        ]

    def _lead_form_field(self, obj):
        field_key = (obj.field_key or "").strip()
        if not field_key:
            return None
        return LeadFormField.objects.filter(
            field_key=field_key,
            is_active=True,
        ).first()

    def get_field_name(self, obj):
        lead_form_field = self._lead_form_field(obj)
        return lead_form_field.field_label if lead_form_field else obj.field_name

    def get_field_type(self, obj):
        lead_form_field = self._lead_form_field(obj)
        return lead_form_field.stage_field_type if lead_form_field else obj.field_type


# =====================================================
# Pipeline Stage READ
# =====================================================
class PipelineStageReadSerializer(serializers.ModelSerializer):
    rules = StageRuleSerializer(many=True, read_only=True)
    fields = StageFieldSerializer(many=True, read_only=True)

    class Meta:
        model = PipelineStage
        fields = [
            "id",
            "stage_name",
            "stage_type",
            "stage_status",
            "stage_order",
            "color_code",
            "entry_rule",

            # ✅ REQUIRED FOR LEAD CONVERSION
            "is_conversion_stage",
            "is_default_stage",

            "rules",
            "fields",
        ]

    # =====================================================
    # RBAC FILTERING
    # =====================================================
    def to_representation(self, instance):
        data = super().to_representation(instance)

        request = self.context.get("request")
        if not request:
            return data

        user = request.user

        # ✅ Admin-like roles → full stage access
        role_name = (
            getattr(getattr(getattr(user, "profile", None), "role", None), "name", "")
            .strip()
            .lower()
            .replace("-", " ")
            .replace("_", " ")
        )
        if role_name in {"super admin", "superadmin", "admin", "clinic admin"}:
            return data

        # ❌ NO PERMISSION → return minimal but stable structure
        if not has_permission(user, "pipeline", "stages", "view"):
            return {
                "id": data.get("id"),
                "stage_name": data.get("stage_name"),
                "stage_type": data.get("stage_type"),
                "stage_status": data.get("stage_status"),
                "stage_order": data.get("stage_order"),
                "color_code": data.get("color_code"),
                "entry_rule": data.get("entry_rule"),

                # ✅ IMPORTANT: keep these visible
                "is_conversion_stage": data.get("is_conversion_stage"),
                "is_default_stage": data.get("is_default_stage"),

                "rules": [],
                "fields": [],
            }

        # 🔥 FIELD FILTERING
        allowed_fields = [
            "id",
            "stage_name",
            "stage_type",
            "stage_status",
            "stage_order",
            "color_code",
            "entry_rule",

            # ✅ REQUIRED
            "is_conversion_stage",
            "is_default_stage",
        ]

        return {k: v for k, v in data.items() if k in allowed_fields}


# =====================================================
# Pipeline READ
# =====================================================
class PipelineReadSerializer(serializers.ModelSerializer):
    stages = serializers.SerializerMethodField()

    class Meta:
        model = Pipeline
        fields = [
            "id",
            "pipeline_name",
            "industry_type",
            "is_active",
            "is_default",
            "stages",
        ]

    def get_stages(self, obj):
        stages = obj.stages.filter(is_deleted=False, is_active=True).order_by("stage_order")
        return PipelineStageReadSerializer(stages, many=True, context=self.context).data


# =====================================================
# Pipeline WRITE
# =====================================================
class PipelineSerializer(serializers.ModelSerializer):
    clinic_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Pipeline
        fields = [
            "id",
            "clinic_id",
            "pipeline_name",
            "industry_type",
            "is_active",
            "is_default",
        ]
        read_only_fields = ("id",)

    # =========================
    # GLOBAL VALIDATION
    # =========================
    def validate(self, attrs):
        request = self.context.get("request")

        # CREATE → clinic required
        if self.instance is None:
            if "clinic_id" not in attrs:
                raise ValidationError({
                    "clinic_id": "This field is required."
                })

        # UPDATE → protect ID & clinic
        if self.instance and request:
            payload_id = request.data.get("id")
            if payload_id and str(payload_id) != str(self.instance.id):
                raise ValidationError({"id": "Pipeline ID mismatch"})

            if "clinic_id" in attrs:
                raise ValidationError({
                    "clinic_id": "clinic_id cannot be changed"
                })

        return attrs

    # =========================
    # CREATE
    # =========================
    def create(self, validated_data):
        return create_pipeline(validated_data)

    # =========================
    # UPDATE
    # =========================
    def update(self, instance, validated_data):
        return update_pipeline(instance, validated_data)
