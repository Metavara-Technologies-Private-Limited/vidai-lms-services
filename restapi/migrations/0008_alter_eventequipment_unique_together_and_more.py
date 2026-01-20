import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('restapi', '0007_alter_eventequipment_unique_together_and_more'),
    ]

    operations = [
        # 1️⃣ ADD equipment_details FIRST
        migrations.AddField(
            model_name='eventequipment',
            name='equipment_details',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='event_equipments',
                to='restapi.equipmentdetails',
                null=True,
            ),
        ),

        # 2️⃣ REMOVE old equipment FK
        migrations.RemoveField(
            model_name='eventequipment',
            name='equipment',
        ),

        # 3️⃣ ADD new unique constraint LAST
        migrations.AlterUniqueTogether(
            name='eventequipment',
            unique_together={('event', 'equipment_details')},
        ),
    ]
