from rest_framework import serializers
from restapi.models import (
    Pipeline,
    PipelineStage,
    StageRule,
    StageField,
)
from restapi.utils.permissions import get_user_permissions, has_permission
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from restapi.models import Pipeline
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
    class Meta:
        model = StageField
        fields = [
            "id",
            "field_name",
            "field_type",
            "is_mandatory",
        ]


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

        # ✅ SUPER ADMIN → FULL ACCESS
        if user.profile.role.name.lower() == "super admin":
            return data

        # ❌ NO PERMISSION → RETURN EMPTY
        if not has_permission(user, "pipeline", "stages", "view"):
            return {}

        # 🔥 FIELD FILTERING
        allowed_fields = [
            "id",
            "stage_name",
            "stage_type",
            "stage_status",
            "stage_order",
            "color_code",
            "entry_rule",
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