from django.db import transaction
from rest_framework.exceptions import ValidationError

from restapi.models import (
    Pipeline,
    PipelineStage,
    StageRule,
    StageField,
    Clinic,
)

# create_pipeline
@transaction.atomic
def create_pipeline(validated_data):
    try:
        clinic = Clinic.objects.get(id=validated_data.pop("clinic_id"))
    except Clinic.DoesNotExist:
        raise ValidationError({"clinic_id": "Invalid clinic_id"})

    pipeline = Pipeline.objects.create(
        clinic=clinic,
        **validated_data
    )

    return pipeline

# update_pipeline
@transaction.atomic
def update_pipeline(instance, validated_data):
    IMMUTABLE_FIELDS = {"clinic", "clinic_id"}

    for field, value in validated_data.items():
        if field in IMMUTABLE_FIELDS:
            continue
        setattr(instance, field, value)

    instance.save()
    instance.refresh_from_db()
    return instance

# add_stage
@transaction.atomic
def add_stage(validated_data):
    try:
        pipeline = Pipeline.objects.get(id=validated_data["pipeline_id"])
    except Pipeline.DoesNotExist:
        raise ValidationError({"pipeline_id": "Invalid pipeline_id"})

    order = (
        PipelineStage.objects
        .filter(pipeline=pipeline)
        .count() + 1
    )

    stage = PipelineStage.objects.create(
        pipeline=pipeline,
        stage_name=validated_data["stage_name"],
        stage_type=validated_data["stage_type"],
        stage_order=order,
        stage_status="open"
    )

    return stage

# update_stage
@transaction.atomic
def update_stage(instance, validated_data):
    IMMUTABLE_FIELDS = {"pipeline"}

    for field, value in validated_data.items():
        if field in IMMUTABLE_FIELDS:
            continue
        setattr(instance, field, value)

    instance.save()
    instance.refresh_from_db()
    return instance

# save_stage_rules
@transaction.atomic
def save_stage_rules(stage, rules_data):
    StageRule.objects.filter(stage=stage).delete()

    for rule in rules_data:
        StageRule.objects.create(
            stage=stage,
            action_type=rule["action_type"],
            is_enabled=rule.get("is_enabled", True),
            is_required=rule.get("is_required", False),
            auto_move=rule.get("auto_move", False),
            allow_manual_move=rule.get("allow_manual_move", True),
        )


# save_stage_fields
@transaction.atomic
def save_stage_fields(stage, fields_data):
    StageField.objects.filter(stage=stage).delete()

    for field in fields_data:
        StageField.objects.create(
            stage=stage,
            field_name=field["field_name"],
            field_type=field["field_type"],
            is_mandatory=field.get("is_mandatory", False),
        )
