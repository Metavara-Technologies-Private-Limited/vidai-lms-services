from django.db import transaction, models
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
        pipeline_id = validated_data.get("pipeline_id") or validated_data.get("pipeline")
        pipeline = Pipeline.objects.get(id=pipeline_id)
    except Pipeline.DoesNotExist:
        raise ValidationError({"pipeline_id": "Invalid pipeline_id"})

    incoming_order = validated_data.get("stage_order")
    if incoming_order is not None:
        order = incoming_order
    else:
        order = (
            PipelineStage.objects
            .filter(pipeline=pipeline, is_deleted=False)
            .count() + 1
        )

    color_code = validated_data.get("color_code") or validated_data.get("stage_color") or "#EBFAEF"
    entry_rule = validated_data.get("entry_rule", "manual")
    stage_status = validated_data.get("stage_status", "open")

    stage = PipelineStage.objects.create(
        pipeline=pipeline,
        stage_name=validated_data["stage_name"],
        stage_type=validated_data["stage_type"],
        stage_order=order,
        stage_status=stage_status,
        color_code=color_code,
        entry_rule=entry_rule,
    )

    return stage

# update_stage
@transaction.atomic
def update_stage(instance, validated_data):
    IMMUTABLE_FIELDS = {"pipeline"}
    MUTABLE_FIELDS = {
        "stage_name",
        "stage_type",
        "stage_status",
        "stage_order",
        "color_code",
        "entry_rule",
        "is_active",
        "is_deleted",
    }

    payload = dict(validated_data)
    if "stage_color" in payload and "color_code" not in payload:
        payload["color_code"] = payload.pop("stage_color")

    for field, value in payload.items():
        if field in IMMUTABLE_FIELDS or field not in MUTABLE_FIELDS:
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
            custom_label=rule.get("custom_label", ""),
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


# duplicate_pipeline
@transaction.atomic
def duplicate_pipeline(pipeline_id):
    try:
        original = Pipeline.objects.get(id=pipeline_id)
    except Pipeline.DoesNotExist:
        raise ValidationError({"pipeline_id": "Pipeline not found"})

    new_pipeline = Pipeline.objects.create(
        clinic=original.clinic,
        pipeline_name=f"{original.pipeline_name} (Copy)",
        industry_type=original.industry_type,
        is_active=original.is_active,
    )

    for stage in original.stages.all():
        new_stage = PipelineStage.objects.create(
            pipeline=new_pipeline,
            stage_name=stage.stage_name,
            stage_type=stage.stage_type,
            stage_status=stage.stage_status,
            stage_order=stage.stage_order,
            color_code=stage.color_code,
            entry_rule=stage.entry_rule,
        )

        for rule in stage.rules.all():
            StageRule.objects.create(
                stage=new_stage,
                action_type=rule.action_type,
                custom_label=rule.custom_label,
                is_enabled=rule.is_enabled,
                is_required=rule.is_required,
                auto_move=rule.auto_move,
                allow_manual_move=rule.allow_manual_move,
            )

        for field in stage.fields.all():
            StageField.objects.create(
                stage=new_stage,
                field_name=field.field_name,
                field_type=field.field_type,
                is_mandatory=field.is_mandatory,
            )

    return new_pipeline


# archive_pipeline
@transaction.atomic
def archive_pipeline(pipeline_id):
    try:
        pipeline = Pipeline.objects.get(id=pipeline_id)
    except Pipeline.DoesNotExist:
        raise ValidationError({"pipeline_id": "Pipeline not found"})

    pipeline.is_active = False
    pipeline.save()
    return pipeline


# delete_pipeline
@transaction.atomic
def delete_pipeline(pipeline_id):
    try:
        pipeline = Pipeline.objects.get(id=pipeline_id)
    except Pipeline.DoesNotExist:
        raise ValidationError({"pipeline_id": "Pipeline not found"})

    pipeline.delete()


# duplicate_stage
@transaction.atomic
def duplicate_stage(stage_id):
    try:
        original = PipelineStage.objects.get(id=stage_id)
    except PipelineStage.DoesNotExist:
        raise ValidationError({"stage_id": "Stage not found"})

    highest_order = PipelineStage.objects.filter(
        pipeline=original.pipeline
    ).aggregate(models.Max("stage_order"))["stage_order__max"] or 0

    new_stage = PipelineStage.objects.create(
        pipeline=original.pipeline,
        stage_name=f"{original.stage_name} (Copy)",
        stage_type=original.stage_type,
        stage_status=original.stage_status,
        stage_order=highest_order + 1,
        color_code=original.color_code,
        entry_rule=original.entry_rule,
    )

    for rule in original.rules.all():
        StageRule.objects.create(
            stage=new_stage,
            action_type=rule.action_type,
            custom_label=rule.custom_label,
            is_enabled=rule.is_enabled,
            is_required=rule.is_required,
            auto_move=rule.auto_move,
            allow_manual_move=rule.allow_manual_move,
        )

    for field in original.fields.all():
        StageField.objects.create(
            stage=new_stage,
            field_name=field.field_name,
            field_type=field.field_type,
            is_mandatory=field.is_mandatory,
        )

    return new_stage


# archive_stage
@transaction.atomic
def archive_stage(stage_id):
    try:
        stage = PipelineStage.objects.get(id=stage_id)
    except PipelineStage.DoesNotExist:
        raise ValidationError({"stage_id": "Stage not found"})

    stage.is_active = False
    stage.save()
    return stage


# delete_stage
@transaction.atomic
def delete_stage(stage_id):
    try:
        stage = PipelineStage.objects.get(id=stage_id)
    except PipelineStage.DoesNotExist:
        raise ValidationError({"stage_id": "Stage not found"})

    stage.delete()