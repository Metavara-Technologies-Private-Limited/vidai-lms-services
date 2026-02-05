from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from restapi.models import (
    Environment,
    Environment_Parameter,
    Environment_Parameter_Value,
)

from restapi.services.environment_service import (
    create_environment,
    update_environment,
)


# =====================================================
# Environment Parameter READ Serializer
# =====================================================
class EnvironmentParameterReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Environment_Parameter
        fields = [
            "id",
            "env_parameter_name",
            "is_active",
            "config",
        ]


# =====================================================
# Environment READ Serializer
# =====================================================
class EnvironmentReadSerializer(serializers.ModelSerializer):
    parameters = serializers.SerializerMethodField()

    class Meta:
        model = Environment
        fields = [
            "id",
            "environment_name",
            "is_active",
            "created_at",
            "parameters",
        ]

    def get_parameters(self, obj):
        qs = (
            obj.parameters
            .filter(is_deleted=False)   # ✅ removed is_active filter
            .order_by("id")
        )
        return EnvironmentParameterReadSerializer(qs, many=True).data


# =====================================================
# Environment Parameter Value READ Serializer
# =====================================================
class EnvironmentParameterValueReadSerializer(serializers.ModelSerializer):
    environment_parameter_id = serializers.IntegerField(
        source="environment_parameter.id",
        read_only=True
    )

    class Meta:
        model = Environment_Parameter_Value
        fields = [
            "id",
            "content",
            "log_time", 
            "created_at",
            "is_deleted",
            "is_active",
            "environment_parameter_id",
        ]


# =====================================================
# Environment Parameter Serializer (WRITE)
# =====================================================
class EnvironmentParameterSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = Environment_Parameter
        fields = [
            "id",                   # ✅ IMPORTANT (ID MUST NOT CHANGE)
            "env_parameter_name",
            "is_active",
            "config",
        ]


# =====================================================
# Environment Parameter PATCH Serializer (ID SAFE)
# =====================================================
class EnvironmentParameterPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Environment_Parameter
        fields = [
            "env_parameter_name",
            "is_active",
            "config",
        ]

    def update(self, instance, validated_data):
        # Update only provided fields (ID never changes)
        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save()
        return instance


# =====================================================
# Environment Serializer
# - Create Environment + Parameters
# - Update Environment + Parameters
# =====================================================
class EnvironmentSerializer(serializers.ModelSerializer):
    environment_name = serializers.CharField(required=False)

    parameters = EnvironmentParameterSerializer(
        many=True,
        required=False
    )

    class Meta:
        model = Environment
        fields = [
            "id",
            "environment_name",
            "is_active",
            "parameters",
        ]

    # ==================================================
    # CREATE (POST)
    # ==================================================
    def create(self, validated_data):
        return create_environment(validated_data)

    # ==================================================
    # UPDATE (PUT / PATCH – STRICT, ID SAFE)
    # ==================================================
    def update(self, instance, validated_data):
        return update_environment(instance, validated_data)


# =====================================================
# Environment Parameter Value Create Serializer
# =====================================================
class EnvironmentParameterValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Environment_Parameter_Value
        fields = [
            "id",
            "log_time", 
            "environment",
            "environment_parameter",
            "content",
        ]

    def validate(self, attrs):
        if (
            attrs["environment_parameter"].environment_id
            != attrs["environment"].id
        ):
            raise ValidationError(
                "Parameter does not belong to this environment"
            )
        return attrs
