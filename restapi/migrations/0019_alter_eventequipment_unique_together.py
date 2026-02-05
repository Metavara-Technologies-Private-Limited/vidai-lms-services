from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('restapi', '0018_alter_eventequipment_unique_together'),
    ]

    operations = [
        # NO-OP migration
        # Unique constraint (event, equipment_details) already exists in DB.
        # This migration is intentionally empty to avoid duplicate constraint errors.
    ]
