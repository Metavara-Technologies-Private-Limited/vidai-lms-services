from django.db import migrations, models


def backfill_pipeline_defaults(apps, schema_editor):
    Pipeline = apps.get_model("restapi", "Pipeline")

    clinic_ids = (
        Pipeline.objects.values_list("clinic_id", flat=True).distinct()
    )

    for clinic_id in clinic_ids:
        clinic_pipelines = Pipeline.objects.filter(clinic_id=clinic_id, is_deleted=False)
        if not clinic_pipelines.exists():
            continue

        # Prefer currently active pipeline as default, then oldest pipeline.
        default_candidate = (
            clinic_pipelines.filter(is_active=True).order_by("created_at", "id").first()
            or clinic_pipelines.order_by("created_at", "id").first()
        )

        clinic_pipelines.update(is_default=False)
        Pipeline.objects.filter(id=default_candidate.id).update(is_default=True)


def reverse_backfill_pipeline_defaults(apps, schema_editor):
    Pipeline = apps.get_model("restapi", "Pipeline")
    Pipeline.objects.update(is_default=False)


class Migration(migrations.Migration):

    dependencies = [
        ("restapi", "0071_campaign_instagram_campaign_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="pipeline",
            name="is_default",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(
            backfill_pipeline_defaults,
            reverse_backfill_pipeline_defaults,
        ),
    ]
