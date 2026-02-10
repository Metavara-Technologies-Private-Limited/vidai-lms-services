from rest_framework import serializers
from restapi.models import (
    Pipeline,
    PipelineStage,
    StageRule,
    StageField,
)

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
            "rules",
            "fields",
        ]


# =====================================================
# Pipeline READ
# =====================================================
class PipelineReadSerializer(serializers.ModelSerializer):
    stages = PipelineStageReadSerializer(many=True, read_only=True)

    class Meta:
        model = Pipeline
        fields = [
            "id",
            "pipeline_name",
            "industry_type",
            "is_active",
            "stages",
        ]


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
