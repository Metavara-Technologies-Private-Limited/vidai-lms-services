from rest_framework import serializers
from django.db import transaction
from .models import Clinic, Department, Equipments, EquipmentDetails, Parameters


class EquipmentDetailSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = EquipmentDetails
        fields = ['id', 'equipment_num', 'make', 'model', 'is_active', 'created_at']
        read_only_fields = ['created_at']


class ParameterSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    content = serializers.JSONField()

    class Meta:
        model = Parameters
        fields = ['id', 'parameter_name', 'is_active', 'content', 'created_at']
        read_only_fields = ['created_at']


class EquipmentSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    equipment_details = EquipmentDetailSerializer(many=True, required=False)
    parameters = ParameterSerializer(many=True, required=False)

    class Meta:
        model = Equipments
        fields = ['id', 'equipment_name', 'created_at', 'equipment_details', 'parameters']
        read_only_fields = ['created_at']

    def _upsert_equipment_details(self, equipment, details_data):
        # Keep track of seen ids
        seen = []
        for d in details_data:
            d_id = d.get('id', None)
            if d_id:
                # update existing
                obj = EquipmentDetails.objects.filter(id=d_id, equipment=equipment).first()
                if obj:
                    for k, v in d.items():
                        if k != 'id':
                            setattr(obj, k, v)
                    obj.save()
                    seen.append(obj.id)
                    continue
            # create new
            new = EquipmentDetails.objects.create(equipment=equipment,equipment_num=d.get('equipment_num'),make=d.get('make'),model=d.get('model'),is_active=d.get('is_active', True))
            seen.append(new.id)
        # delete omitted details
        EquipmentDetails.objects.filter(equipment=equipment).exclude(id__in=seen).delete()

    def _upsert_parameters(self, equipment, params_data):
        seen = []
        for p in params_data:
            p_id = p.get('id', None)
            if p_id:
                obj = Parameters.objects.filter(id=p_id, equipment=equipment).first()
                if obj:
                    for k, v in p.items():
                        if k != 'id':
                            setattr(obj, k, v)
                    obj.save()
                    seen.append(obj.id)
                    continue
            # create new
            new = Parameters.objects.create(equipment=equipment,parameter_name=p.get('parameter_name'),content=p.get('content', {}),is_active=p.get('is_active', True))
            seen.append(new.id)
        Parameters.objects.filter(equipment=equipment).exclude(id__in=seen).delete()

    def create(self, validated_data):
        details = validated_data.pop('equipment_details', [])
        params = validated_data.pop('parameters', [])
        # department (dep) is handled in Department serializer
        equipment = Equipments.objects.create(**validated_data)
        if details:
            for d in details:
                EquipmentDetails.objects.create(equipment=equipment,equipment_num=d.get('equipment_num'),make=d.get('make'),model=d.get('model'),is_active=d.get('is_active', True))
        if params:
            for p in params:
                Parameters.objects.create(equipment=equipment,parameter_name=p.get('parameter_name'),content=p.get('content', {}),is_active=p.get('is_active', True))
        return equipment

    def update(self, instance, validated_data):
        details = validated_data.pop('equipment_details', [])
        params = validated_data.pop('parameters', [])

        # update simple fields
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()

        # upsert details and params
        if details is not None:
            self._upsert_equipment_details(instance, details)
        if params is not None:
            self._upsert_parameters(instance, params)
        return instance


class DepartmentSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    equipments = EquipmentSerializer(many=True, required=False)

    class Meta:
        model = Department
        fields = ['id', 'name', 'is_active', 'created_at', 'equipments']
        read_only_fields = ['created_at']

    def _upsert_equipments(self, department, equipments_data):
        seen = []
        for e in equipments_data:
            e_id = e.get('id', None)
            equip_serializer = EquipmentSerializer()
            if e_id:
                obj = Equipments.objects.filter(id=e_id, dep=department).first()
                if obj:
                    # update existing equipment (EquipmentSerializer.update expects instance and validated_data)
                    # but here e includes nested lists; use serializer.update
                    equip_serializer.update(obj, e)
                    seen.append(obj.id)
                    continue
            # create new equipment
            details = e.pop('equipment_details', [])
            params = e.pop('parameters', [])
            new_eq = Equipments.objects.create(dep=department, **e)
            for d in details:
                EquipmentDetails.objects.create(equipment=new_eq,equipment_num=d.get('equipment_num'),make=d.get('make'),model=d.get('model'),is_active=d.get('is_active', True))
            for p in params:
                Parameters.objects.create(equipment=new_eq,parameter_name=p.get('parameter_name'),content=p.get('content', {}),is_active=p.get('is_active', True))
            seen.append(new_eq.id)
        # delete omitted equipments (cascades will remove detail/params)
        Equipments.objects.filter(dep=department).exclude(id__in=seen).delete()

    def create(self, validated_data):
        equipments_data = validated_data.pop('equipments', [])
        # clinic must be set by parent serializer (ClinicSerializer.create)
        department = Department.objects.create(**validated_data)
        for e in equipments_data:
            details = e.pop('equipment_details', [])
            params = e.pop('parameters', [])
            equipment = Equipments.objects.create(dep=department, **e)
            for d in details:
                EquipmentDetails.objects.create(equipment=equipment,equipment_num=d.get('equipment_num'),make=d.get('make'),model=d.get('model'),is_active=d.get('is_active', True))
            for p in params:
                Parameters.objects.create(equipment=equipment,parameter_name=p.get('parameter_name'),content=p.get('content', {}),is_active=p.get('is_active', True))
        return department

    def update(self, instance, validated_data):
        equipments_data = validated_data.pop('equipments', None)

        # update simple fields
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()

        if equipments_data is not None:
            self._upsert_equipments(instance, equipments_data)

        return instance


class ClinicSerializer(serializers.ModelSerializer):
    clinic = serializers.SerializerMethodField(read_only=True)  # for response shape compatibility if needed
    # We'll accept nested departments under key "department" per your JSON
    department = DepartmentSerializer(many=True, required=False)

    class Meta:
        model = Clinic
        # Using 'clinic' wrapper in output to match your JSON if you want; but typical APIs return top-level fields.
        fields = ['id', 'name', 'clinic', 'department']
        read_only_fields = ['clinic']

    def get_clinic(self, obj):
        # Represent clinic as object under "clinic" to match your input shape if you want the response to mirror request
        return {
            'id': obj.id,
            'name': obj.name
        }

    @transaction.atomic
    def create(self, validated_data):
        departments_data = validated_data.pop('department', [])
        # create clinic (client provides id)
        clinic = Clinic.objects.create(**validated_data)

        for d in departments_data:
            equipments = d.pop('equipments', [])
            # attach clinic foreign key
            department = Department.objects.create(clinic=clinic, **d)
            for e in equipments:
                details = e.pop('equipment_details', [])
                params = e.pop('parameters', [])
                equipment = Equipments.objects.create(dep=department, **e)
                for detail in details:
                    EquipmentDetails.objects.create(equipment=equipment,equipment_num=detail.get('equipment_num'),make=detail.get('make'),model=detail.get('model'),is_active=detail.get('is_active', True))
                for p in params:
                    Parameters.objects.create(equipment=equipment,parameter_name=p.get('parameter_name'),content=p.get('content', {}),is_active=p.get('is_active', True))
        return clinic

    @transaction.atomic
    def update(self, instance, validated_data):
        # Merge semantics by id; delete omitted nested children
        departments_data = validated_data.pop('department', None)

        # update clinic fields (id should not change)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()

        if departments_data is not None:
            # Process departments: update existing by id, create new, collect seen ids
            seen_dept_ids = []
            for d in departments_data:
                d_id = d.get('id', None)
                equipments = d.pop('equipments', [])
                if d_id:
                    dept_obj = Department.objects.filter(id=d_id, clinic=instance).first()
                    if dept_obj:
                        # update fields on department
                        for k, v in d.items():
                            setattr(dept_obj, k, v)
                        dept_obj.save()
                        # upsert equipments under this department
                        DepartmentSerializer()._upsert_equipments(dept_obj, equipments)
                        seen_dept_ids.append(dept_obj.id)
                        continue
                # create new department
                new_dept = Department.objects.create(clinic=instance, **d)
                # create equipments under it
                for e in equipments:
                    details = e.pop('equipment_details', [])
                    params = e.pop('parameters', [])
                    new_e = Equipments.objects.create(dep=new_dept, **e)
                    for detail in details:
                        EquipmentDetails.objects.create(equipment=new_e,equipment_num=detail.get('equipment_num'),make=detail.get('make'),model=detail.get('model'),is_active=detail.get('is_active', True))
                    for p in params:
                        Parameters.objects.create(equipment=new_e,parameter_name=p.get('parameter_name'),content=p.get('content', {}),is_active=p.get('is_active', True))
                seen_dept_ids.append(new_dept.id)
            # delete departments not in payload (cascades to equipments/details/params)
            Department.objects.filter(clinic=instance).exclude(id__in=seen_dept_ids).delete()

        return instance
class EquipmentDetailReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentDetails
        fields = ['id', 'equipment_num', 'make', 'model', 'is_active']
class ParameterReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parameters
        fields = ['id', 'parameter_name', 'is_active', 'content']

class EquipmentReadSerializer(serializers.ModelSerializer):
    equipment_details = EquipmentDetailReadSerializer(many=True, source='equipmentdetails_set')
    parameters = ParameterReadSerializer(many=True, source='parameters_set')

    class Meta:
        model = Equipments
        fields = ['id', 'equipment_name', 'equipment_details', 'parameters']

class DepartmentReadSerializer(serializers.ModelSerializer):
    equipments = EquipmentReadSerializer(many=True, source='equipments_set')

    class Meta:
        model = Department
        fields = ['id', 'name', 'is_active', 'equipments']

class ClinicReadSerializer(serializers.ModelSerializer):
    department = DepartmentReadSerializer(many=True, source='department_set')

    class Meta:
        model = Clinic
        fields = ['id', 'name', 'department']