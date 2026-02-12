from django.db import transaction
from rest_framework.exceptions import ValidationError

from restapi.models import (
    TemplateMail,
    TemplateSMS,
    TemplateWhatsApp,
)


@transaction.atomic
def create_template(template_type, validated_data):

    if template_type == "mail":
        return TemplateMail.objects.create(**validated_data)

    elif template_type == "sms":
        return TemplateSMS.objects.create(**validated_data)

    elif template_type == "whatsapp":
        return TemplateWhatsApp.objects.create(**validated_data)

    else:
        raise ValidationError("Invalid template type.")


@transaction.atomic
def update_template(template_type, instance, validated_data):

    for field, value in validated_data.items():
        setattr(instance, field, value)

    instance.save()
    instance.refresh_from_db()

    return instance
