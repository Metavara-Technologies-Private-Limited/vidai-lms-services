from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('restapi', '0007_alter_eventequipment_unique_together_and_more'),
    ]

    # NOTE:
    # This migration originally:
    # - Added equipment_details
    # - Removed old equipment FK
    # - Updated unique_together
    #
    # These changes are already reflected in DB and models.
    # Keeping this migration as a NO-OP avoids state replay errors.

    operations = []
