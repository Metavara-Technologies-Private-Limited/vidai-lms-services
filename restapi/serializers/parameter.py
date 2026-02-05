from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.utils import timezone

from restapi.models import Parameters, ParameterValues
from restapi.services.parameter_service import (
    validate_parameter_soft_delete,
    soft_delete_parameter,
)


# =====================================================
# Parameter Value Serializer (READ / CREATE)
# =====================================================
class ParameterValueSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = ParameterValues
        fields = [
            "id",
            "content",
            "created_at",
            "is_deleted",
        ]
        read_only_fields = [
            "created_at",
            "is_deleted",
        ]


# =====================================================
# Parameter Serializer
# =====================================================
class ParameterSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = Parameters
        fields = [
            "id",                 # ✅ REQUIRED
            "parameter_name",
            "is_active",
            "config",
        ]


# =====================================================
# parameter Value Create Serializer
# =====================================================
class ParameterValueCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParameterValues
        fields = [
            "id",
            "log_time",
            "parameter",
            "equipment_details",
            "content",
        ]


# =========================
# Parameter Soft Delete Serializer
# =========================
class ParameterSoftDeleteSerializer(serializers.Serializer):
    parameter_id = serializers.IntegerField()

    def validate(self, attrs):
        return validate_parameter_soft_delete(attrs)

    def save(self):
        return soft_delete_parameter(self.validated_data)


# =====================================================
# Parameter Toggle Serializer
# =====================================================
class ParameterToggleSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["equipment", "environment"])
    parameter_id = serializers.IntegerField()


class ParameterValueReadSerializer(serializers.ModelSerializer):
    equipment_details_id = serializers.IntegerField(
        source="equipment_details.id",
        read_only=True
    )
    parameter_id = serializers.IntegerField(
        source="parameter.id",
        read_only=True
    )

    class Meta:
        model = ParameterValues
        fields = [
            "id",
            "content",
            "log_time",
            "created_at",
            "is_deleted",
            "equipment_details_id",
            "parameter_id",
        ]


# =====================================================
# Parameter READ Serializer (NO parameter_values)
# =====================================================
class ParameterReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parameters
        fields = [
            "id",
            "parameter_name",
            "is_active",
            "config",
        ]
