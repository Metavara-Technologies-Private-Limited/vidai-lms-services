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

    class Meta:
        model = Parameters
        fields = ["id", "parameter_name", "format", "is_active"]




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
        dep = validated_data.pop("dep")

        equipment = Equipments.objects.create(dep=dep, **validated_data)

        for d in details:
            EquipmentDetails.objects.create(equipment=equipment, **d)

        for p in params:
            parameter = Parameters.objects.create(
                equipment=equipment,
                parameter_name=p.get("parameter_name"),
                format=p.get("format"),
                is_active=p.get("is_active", True)
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

        # 🔹 KRISHNA RULE IMPLEMENTED HERE
        for p in params:
            param_id = p.get("id")

            # ❌ No id → skip silently
            if not param_id:
                continue

            try:
                parameter = Parameters.objects.get(
                    id=param_id,
                    equipment=instance
                )
            except Parameters.DoesNotExist:
                continue  # ❌ no error

            # ✅ UPDATE PARAMETERS TABLE
            if "parameter_name" in p:
                parameter.parameter_name = p.get("parameter_name")

            if "format" in p:
                parameter.format = p.get("format")

            if "is_active" in p:
                parameter.is_active = p.get("is_active")

            parameter.save()

            # ✅ UPDATE PARAMETER VALUES ONLY IF PROVIDED
            values = p.get("parameter_values", [])
            for v in values:
                ParameterValues.objects.create(
                    parameter=parameter,
                    content=v.get("content")
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
    department = serializers.SerializerMethodField()

    class Meta:
        model = Clinic
        fields = ["id", "name", "department"]

    # 🔹 DISPLAY departments (GET)
    def get_department(self, obj):
        return DepartmentReadSerializer(
            obj.department_set.all(),
            many=True
        ).data

    # 🔹 CREATE (POST)
    @transaction.atomic
    def create(self, validated_data):
        departments_data = self.initial_data.get("department", [])

        clinic = Clinic.objects.create(
            name=validated_data.get("name")
        )

        for d in departments_data:
            department = Department.objects.create(
                clinic=clinic,
                name=d.get("name"),
                is_active=d.get("is_active", True)
            )

            for e in d.get("equipments", []):
                equipment = Equipments.objects.create(
                    dep=department,
                    equipment_name=e.get("equipment_name"),
                    is_active=e.get("is_active", True)
                )

                # ✅ ADDED HERE — SAVE EQUIPMENT DETAILS
                for det in e.get("equipment_details", []):
                    EquipmentDetails.objects.create(
                        equipment=equipment,
                        equipment_num=det.get("equipment_num"),
                        make=det.get("make"),
                        model=det.get("model"),
                        is_active=det.get("is_active", True)
                    )

                # Parameters
                for p in e.get("parameters", []):
                    Parameters.objects.create(
                        equipment=equipment,
                        parameter_name=p.get("parameter_name"),
                        format=p.get("format"),
                        is_active=p.get("is_active", True)
                    )

        return clinic

    # 🔹 UPDATE (PUT) — FULL REPLACE
    @transaction.atomic
    def update(self, instance, validated_data):
        departments_data = self.initial_data.get("department", [])

        # FULL REPLACE
        Department.objects.filter(clinic=instance).delete()

        instance.name = validated_data.get("name", instance.name)
        instance.save()

        for d in departments_data:
            department = Department.objects.create(
                clinic=instance,
                name=d.get("name"),
                is_active=d.get("is_active", True)
            )

            for e in d.get("equipments", []):
                equipment = Equipments.objects.create(
                    dep=department,
                    equipment_name=e.get("equipment_name"),
                    is_active=e.get("is_active", True)
                )

                # ✅ ADDED HERE — SAVE EQUIPMENT DETAILS
                for det in e.get("equipment_details", []):
                    EquipmentDetails.objects.create(
                        equipment=equipment,
                        equipment_num=det.get("equipment_num"),
                        make=det.get("make"),
                        model=det.get("model"),
                        is_active=det.get("is_active", True)
                    )

                # Parameters
                for p in e.get("parameters", []):
                    Parameters.objects.create(
                        equipment=equipment,
                        parameter_name=p.get("parameter_name"),
                        format=p.get("format"),
                        is_active=p.get("is_active", True)
                    )

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
    format = serializers.JSONField()

    parameter_values = ParameterValueReadSerializer(many=True)

    class Meta:
        model = Parameters
        fields = [
            "id",
            "parameter_name",
            "format",
            "is_active",
            "parameter_values"
        ]



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






