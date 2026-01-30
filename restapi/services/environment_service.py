from django.db import transaction
from rest_framework.exceptions import ValidationError

from restapi.models import (
    Environment,
    Environment_Parameter,
)


# ==================================================
# CREATE (POST)
# ==================================================
@transaction.atomic
def create_environment(validated_data):
    parameters_data = validated_data.pop("parameters", [])
    department = validated_data.pop("dep")

    environment = Environment.objects.create(
        dep=department,
        **validated_data
    )

    for param in parameters_data:
        Environment_Parameter.objects.create(
            environment=environment,
            env_parameter_name=param["env_parameter_name"],
            is_active=param.get("is_active", True),
            config=param.get("config"),
        )

    environment.refresh_from_db()
    return environment


# ==================================================
# UPDATE (PUT / PATCH – STRICT, ID SAFE)
# ==================================================
@transaction.atomic
def update_environment(instance, validated_data):
    parameters_data = validated_data.pop("parameters", [])

    # ----------------------------
    # Update Environment fields
    # ----------------------------
    if "environment_name" in validated_data:
        instance.environment_name = validated_data["environment_name"]

    if "is_active" in validated_data:
        instance.is_active = validated_data["is_active"]

    instance.save()

    # ==================================================
    # Parameters (STRICT — SAME AS EQUIPMENT)
    # ==================================================
    for param in parameters_data:
        param_id = param.get("id")

        if param_id:
            # 🔒 Update existing parameter ONLY
            try:
                param_instance = Environment_Parameter.objects.get(
                    id=param_id,
                    environment=instance
                )
            except Environment_Parameter.DoesNotExist:
                raise ValidationError(
                    f"Invalid environment parameter id {param_id}"
                )

            param_instance.env_parameter_name = param.get(
                "env_parameter_name",
                param_instance.env_parameter_name
            )
            param_instance.is_active = param.get(
                "is_active",
                param_instance.is_active
            )

            if "config" in param:
                param_instance.config = param["config"]

            param_instance.save()

        else:
            # 🆕 Create new parameter
            Environment_Parameter.objects.create(
                environment=instance,
                env_parameter_name=param["env_parameter_name"],
                is_active=param.get("is_active", True),
                config=param.get("config"),
            )

    instance.refresh_from_db()
    return instance
