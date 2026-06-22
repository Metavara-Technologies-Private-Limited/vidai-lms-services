from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("restapi", "0080_leadformfield_stagefield_field_key"),
    ]

    operations = [
        migrations.CreateModel(
            name="LeadCustomFieldValue",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("value", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("modified_at", models.DateTimeField(auto_now=True)),
                ("field", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lead_values", to="restapi.leadformfield")),
                ("lead", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="custom_field_values", to="restapi.lead")),
            ],
            options={
                "db_table": "restapi_lead_custom_field_value",
                "unique_together": {("lead", "field")},
            },
        ),
        migrations.AddIndex(
            model_name="leadcustomfieldvalue",
            index=models.Index(fields=["lead", "field"], name="restapi_lea_lead_id_963f6c_idx"),
        ),
    ]
