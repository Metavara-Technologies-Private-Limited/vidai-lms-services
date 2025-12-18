from rest_framework import serializers
from django.db import transaction
from .models import (
    Clinic, Department, Equipments,
    EquipmentDetails, Parameters, ParameterValues
)


# =========================
# Equipment Details
# =========================
class EquipmentDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentDetails
        fields = ['equipment_num', 'make', 'model', 'is_active']


# =========================
# Parameter Values (NEW)
# =========================
class ParameterValueSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = ParameterValues
        fields = ['id', 'content', 'created_at', 'is_deleted']
        read_only_fields = ['created_at', 'is_deleted']



# =========================
# Parameters
# =========================
class ParameterSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    parameter_values = ParameterValueSerializer(many=True, required=False)

    class Meta:
        model = Parameters
        fields = ["id", "parameter_name", "is_active", "parameter_values"]
        



# =========================
# Equipments
# =========================
class EquipmentSerializer(serializers.ModelSerializer):
    equipment_details = EquipmentDetailSerializer(many=True, required=False)
    parameters = ParameterSerializer(many=True, required=False)

    class Meta:
        model = Equipments
        fields = [
            "id", "equipment_name", "is_active",
            "equipment_details", "parameters"
        ]

    # -------- CREATE --------
    @transaction.atomic
    def create(self, validated_data):
        details = validated_data.pop("equipment_details", [])
        params = validated_data.pop("parameters", [])

        dep = validated_data.pop("dep")  #  REQUIRED FIX

        equipment = Equipments.objects.create(
            dep=dep,
            **validated_data
        )

        for d in details:
            EquipmentDetails.objects.create(
                equipment=equipment,
                **d
            )

        for p in params:
            values = p.pop("parameter_values", [])

            parameter = Parameters.objects.create(
                equipment=equipment,
                parameter_name=p["parameter_name"],
                is_active=p.get("is_active", True)
            )

            for v in values:
                ParameterValues.objects.create(
                    parameter=parameter,
                    content=v["content"]
                )

        return equipment

    # -------- UPDATE --------
    @transaction.atomic
    def update(self, instance, validated_data):
        params = validated_data.pop("parameters", [])
        details = validated_data.pop("equipment_details", [])

        instance.equipment_name = validated_data.get(
            "equipment_name", instance.equipment_name
        )
        instance.is_active = validated_data.get(
            "is_active", instance.is_active
        )
        instance.save()

        for d in details:
            EquipmentDetails.objects.create(
                equipment=instance,
                **d
            )

        for p in params:
            param_id = p.get("id")
            values = p.get("parameter_values", [])

            if not param_id:
                raise serializers.ValidationError(
                    "Parameter id is required for update"
                )

            #  SAFE GET
            try:
                parameter = Parameters.objects.get(
                    id=param_id,
                    equipment=instance
                )
            except Parameters.DoesNotExist:
                raise serializers.ValidationError(
                    f"Parameter with id {param_id} not found"
                )

            #  APPEND HISTORY
            for v in values:
                ParameterValues.objects.create(
                    parameter=parameter,
                    content=v["content"]
                )

        return instance

# =========================
# Department
# =========================
class DepartmentSerializer(serializers.ModelSerializer):
    equipments = EquipmentSerializer(many=True, required=False)

    class Meta:
        model = Department
        fields = ['id', 'name', 'is_active', 'equipments']

    def create(self, validated_data):
        equipments_data = validated_data.pop('equipments', [])
        department = Department.objects.create(**validated_data)

        for e in equipments_data:
            EquipmentSerializer().create({**e, 'dep': department})

        return department


# =========================
# Clinic
# =========================
class ClinicSerializer(serializers.ModelSerializer):
    department = DepartmentSerializer(many=True, required=False)

    class Meta:
        model = Clinic
        fields = ['id', 'name', 'department']

    @transaction.atomic
    def create(self, validated_data):
        departments = validated_data.pop('department', [])
        clinic = Clinic.objects.create(**validated_data)

        for d in departments:
            equipments = d.pop('equipments', [])
            department = Department.objects.create(clinic=clinic, **d)

            for e in equipments:
                EquipmentSerializer().create({**e, 'dep': department})

        return clinic


# =====================================================
# READ SERIALIZERS
# =====================================================
class EquipmentDetailReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentDetails
        fields = ['id', 'equipment_num', 'make', 'model', 'is_active']

class ParameterValueReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParameterValues
        fields = ['id', 'content', 'created_at', 'is_deleted']


class ParameterReadSerializer(serializers.ModelSerializer):
    parameter_values = ParameterValueReadSerializer(many=True)
    class Meta:
        model = Parameters
        fields = ['id', 'parameter_name', 'is_active', 'parameter_values']
   


class EquipmentReadSerializer(serializers.ModelSerializer):
    equipment_details = EquipmentDetailReadSerializer(many=True, source='equipmentdetails_set')
    parameters = ParameterReadSerializer(many=True, source='parameters_set')

    class Meta:
        model = Equipments
        fields = ['id', 'equipment_name', 'equipment_details', 'parameters']


class DepartmentReadSerializer(serializers.ModelSerializer):

    #  ADDED: use method field to control queryset
    equipments = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = ['id', 'name', 'is_active', 'equipments']

    #  ADDED: hide soft-deleted equipments
    def get_equipments(self, obj):
        qs = obj.equipments_set.filter(is_deleted=False)  #  ADDED FILTER
        return EquipmentReadSerializer(qs, many=True).data


class ClinicReadSerializer(serializers.ModelSerializer):
    department = DepartmentReadSerializer(many=True, source='department_set')

    class Meta:
        model = Clinic
        fields = ['id', 'name', 'department']






