from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('restapi', '0056_alter_templatesms_use_case'),
    ]

    operations = [
        migrations.AlterField(
            model_name='templatemail',
            name='use_case',
            field=models.ForeignKey(
                to='restapi.usecase',
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
            ),
        ),
    ]