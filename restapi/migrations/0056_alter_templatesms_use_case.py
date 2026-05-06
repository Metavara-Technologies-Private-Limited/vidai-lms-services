from django.db import migrations, models
import django.db.models.deletion


def clean_use_case_data(apps, schema_editor):

    # ---- SMS TABLE ----
    schema_editor.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='restapi_template_sms'
                AND column_name='use_case'
                AND is_nullable='NO'
            ) THEN
                ALTER TABLE restapi_template_sms
                ALTER COLUMN use_case DROP NOT NULL;
            END IF;
        END$$;
    """)

    schema_editor.execute("""
        UPDATE restapi_template_sms
        SET use_case = NULL
        WHERE use_case IS NOT NULL
        AND use_case !~ '^[0-9a-fA-F-]{36}$';
    """)

    # ---- MAIL TABLE ----
    schema_editor.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='restapi_template_mail'
                AND column_name='use_case'
                AND is_nullable='NO'
            ) THEN
                ALTER TABLE restapi_template_mail
                ALTER COLUMN use_case DROP NOT NULL;
            END IF;
        END$$;
    """)

    schema_editor.execute("""
        UPDATE restapi_template_mail
        SET use_case = NULL
        WHERE use_case IS NOT NULL
        AND use_case !~ '^[0-9a-fA-F-]{36}$';
    """)


class Migration(migrations.Migration):

    dependencies = [
        ('restapi', '0055_usecase_alter_templatewhatsapp_use_case_interest'),
    ]

    operations = [
        migrations.RunPython(clean_use_case_data),

        migrations.AlterField(
            model_name='templatesms',
            name='use_case',
            field=models.ForeignKey(
                to='restapi.usecase',
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='sms_templates',
            ),
        ),
    ]