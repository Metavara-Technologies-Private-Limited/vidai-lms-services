from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("restapi", "0072_pipeline_is_default"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="pipeline",
            constraint=models.UniqueConstraint(
                fields=("clinic",),
                condition=Q(is_default=True),
                name="uniq_default_pipeline_per_clinic",
            ),
        ),
    ]
