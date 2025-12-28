from rest_framework import serializers
from django.db import transaction
from .models import (
    Clinic, Department, Equipments,
    EquipmentDetails, Parameters, ParameterValues
)

# =====================================================
# Equipment Details Serializer
# =====================================================
class EquipmentDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentDetails
        fields = ['equipment_num', 'make', 'model', 'is_active']


# =====================================================
# Parameter Value Serializer
# =====================================================
class ParameterValueSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = ParameterValues
        fields = ['id', 'content', 'created_at', 'is_deleted']
        read_only_fields = ['created_at', 'is_deleted']


# =====================================================
# Parameter Serializer
# =====================================================
class ParameterSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    parameter_values = ParameterValueSerializer(many=True, required=False)

    # Optional alias field (frontend may send `format`)
    format = serializers.JSONField(write_only=True, required=False)

    class Meta:
        model = Parameters
        fields = [
            "id",
            "parameter_name",
            "is_active",
            "parameter_values",
            "format"
        ]


# =====================================================
# Equipment Serializer
# =====================================================
class EquipmentSerializer(serializers.ModelSerializer):
    equipment_details = EquipmentDetailSerializer(many=True, required=False)
    parameters = ParameterSerializer(many=True, required=False)

    class Meta:
        model = Equipments
        fields = [
            'id',
            'equipment_name',
            'is_active',
            'equipment_details',
            'parameters'
        ]

    # -------------------------------------------------
    # CREATE Equipment
    # -------------------------------------------------
    @transaction.atomic
    def create(self, validated_data):
        equipment_details_data = validated_data.pop("equipment_details", [])
        parameters_data = validated_data.pop("parameters", [])
        department = validated_data.pop("dep")  # injected from view

        equipment = Equipments.objects.create(
            dep=department,
            **validated_data
        )

        # ---------- Create Equipment Details ----------
        for equipment_detail in equipment_details_data:
            EquipmentDetails.objects.create(
                equipment=equipment,
                **equipment_detail
            )

        # ---------- Create Parameters ----------
        for parameter_data in parameters_data:
            parameter_values_data = parameter_data.pop("parameter_values", [])

            # VALIDATION:
            # If both parameter_values and format are missing
            # DRF will return HTTP 400 to frontend
            if not parameter_values_data and "format" not in parameter_data:
                raise serializers.ValidationError({
                    "parameter_values": "Parameter values cannot be empty"
                })

            # Support `format` as alias
            if not parameter_values_data and "format" in parameter_data:
                parameter_values_data = [{"content": parameter_data.pop("format")}]

            parameter = Parameters.objects.create(
                equipment=equipment,
                parameter_name=parameter_data["parameter_name"],
                is_active=parameter_data.get("is_active", True)
            )

            for parameter_value in parameter_values_data:
                ParameterValues.objects.create(
                    parameter=parameter,
                    content=parameter_value["content"]
                )

        return equipment

    # -------------------------------------------------
    # UPDATE Equipment (APPEND ONLY)
    # -------------------------------------------------
    @transaction.atomic
    def update(self, instance, validated_data):
        equipment_details_data = validated_data.pop("equipment_details", [])
        parameters_data = validated_data.pop("parameters", [])

        instance.equipment_name = validated_data.get(
            "equipment_name", instance.equipment_name
        )
        instance.is_active = validated_data.get(
            "is_active", instance.is_active
        )
        instance.save()

        # ---------- Append Equipment Details ----------
        for equipment_detail in equipment_details_data:
            EquipmentDetails.objects.create(
                equipment=instance,
                **equipment_detail
            )

        # ---------- Append Parameter Values ----------
        for parameter_data in parameters_data:
            param_id = parameter_data.get("id")
            parameter_values_data = parameter_data.get("parameter_values", [])

            # VALIDATION 1:
            # Parameter ID must be provided
            if not param_id:
                raise serializers.ValidationError({
                    "parameter_id": "Parameter id is required for update"
                })

            # VALIDATION 2:
            # Parameter must belong to this equipment (PARENT VALIDATION)
            try:
                parameter = Parameters.objects.get(
                    id=param_id,
                    equipment=instance
                )
            except Parameters.DoesNotExist:
                raise serializers.ValidationError({
                    "parameter_id": f"Parameter with id {param_id} not found for this equipment"
                })

            # VALIDATION 3:
            # Parameter values must not be empty
            if not parameter_values_data:
                raise serializers.ValidationError({
                    "parameter_values": "Parameter values cannot be empty"
                })

            for parameter_value in parameter_values_data:
                ParameterValues.objects.create(
                    parameter=parameter,
                    content=parameter_value["content"]
                )

        return instance


# =====================================================
# Department Serializer
# =====================================================
class DepartmentSerializer(serializers.ModelSerializer):
    equipments = EquipmentSerializer(many=True, required=False)

    class Meta:
        model = Department
        fields = ['id', 'name', 'is_active', 'equipments']

    @transaction.atomic
    def create(self, validated_data):
        equipments_data = validated_data.pop('equipments', [])
        department = Department.objects.create(**validated_data)

        for equipment_data in equipments_data:
            EquipmentSerializer().create({
                **equipment_data,
                'dep': department
            })

        return department


# =====================================================
# Clinic Serializer
# =====================================================
class ClinicSerializer(serializers.ModelSerializer):
    department = DepartmentSerializer(many=True, required=False)

    class Meta:
        model = Clinic
        fields = ['id', 'name', 'department']

    # ---------------- CREATE Clinic ----------------
    @transaction.atomic
    def create(self, validated_data):
        departments_data = validated_data.pop('department', [])
        clinic = Clinic.objects.create(**validated_data)

        for department_data in departments_data:
            equipments_data = department_data.pop('equipments', [])

            department = Department.objects.create(
                clinic=clinic,
                name=department_data.get('name'),
                is_active=department_data.get('is_active', True)
            )

            for equipment_data in equipments_data:
                EquipmentSerializer().create({
                    **equipment_data,
                    'dep': department
                })

        return clinic

    # ---------------- UPDATE Clinic ----------------
    @transaction.atomic
    def update(self, instance, validated_data):
        departments_data = validated_data.pop('department', [])

        Department.objects.filter(clinic=instance).delete()

        instance.name = validated_data.get('name', instance.name)
        instance.save()

        for department_data in departments_data:
            equipments_data = department_data.pop('equipments', [])

            department = Department.objects.create(
                clinic=instance,
                name=department_data.get('name'),
                is_active=department_data.get('is_active', True)
            )

            for equipment_data in equipments_data:
                EquipmentSerializer().create({
                    **equipment_data,
                    'dep': department
                })

        return instance


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






