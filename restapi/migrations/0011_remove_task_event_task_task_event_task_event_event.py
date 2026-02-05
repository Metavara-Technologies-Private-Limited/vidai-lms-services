from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('restapi', '0010_environment_parameter_value_log_time_and_more'),
    ]

    # NOTE:
    # This migration originally removed the 'event' field.
    # The field no longer exists and DB is already correct.
    # Converted to NO-OP to avoid migration state errors.

    operations = []
