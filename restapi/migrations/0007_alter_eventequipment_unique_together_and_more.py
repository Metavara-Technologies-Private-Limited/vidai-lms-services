from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('restapi', '0006_environment_environment_parameter_and_more'),
    ]

    operations = [
        # 🔥 STEP 1: remove OLD unique constraint (event, equipment)
        migrations.AlterUniqueTogether(
            name='eventequipment',
            unique_together=set(),
        ),
    ]
