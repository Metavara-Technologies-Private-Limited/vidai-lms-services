from rest_framework.exceptions import ValidationError
from django.utils import timezone

from restapi.models import Parameters


def validate_parameter_soft_delete(attrs):
    try:
        parameter = Parameters.objects.get(
            id=attrs["parameter_id"],
            is_deleted=False
        )
    except Parameters.DoesNotExist:
        raise ValidationError("Invalid or already deleted parameter")

    attrs["parameter"] = parameter
    return attrs


def soft_delete_parameter(validated_data):
    parameter = validated_data["parameter"]

    parameter.is_deleted = True
    parameter.is_active = False
    parameter.deleted_at = timezone.now()

    parameter.save(
        update_fields=["is_deleted", "is_active", "deleted_at"]
    )

    return parameter
