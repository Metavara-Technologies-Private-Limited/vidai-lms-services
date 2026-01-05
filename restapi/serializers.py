from rest_framework import serializers
from django.db import transaction
from .models import (
    Clinic, Department, Equipments,
    EquipmentDetails, Parameters, ParameterValues, Event,
    EventSchedule,
    EventEquipment,
    Department,
    Employee,
    Equipments,
    Task,
    SubTask,
    Document,
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

class EventScheduleReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventSchedule
        fields = [
            "type",
            "from_time",
            "to_time",
            "one_time_date",
            "start_date",
            "end_date",
            "months",
            "days",
            "recurring_duration"
        ]

class SubTaskReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubTask
        fields = [
            "id",
            "assignment",
            "due_date",
            "description",
            "status",
            "created_at"
        ]

class DocumentReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id",
            "document_name",
            "created_at"
        ]




class TaskReadSerializer(serializers.ModelSerializer):
    sub_tasks = SubTaskReadSerializer(
        source="subtask_set",
        many=True
    )
    documents = DocumentReadSerializer(
        source="document_set",
        many=True
    )

    class Meta:
        model = Task
        fields = [
            "id",
            "event",
            "assignment",
            "due_date",
            "description",
            "status",
            "sub_tasks",
            "documents",
            "created_at",
            "modified_at"
        ]

class EmployeeReadSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="dep.name", read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "emp_name",
            "emp_type",
            "department_name"
        ]


# =========================
# Event READ Serializer
# =========================
class EventReadSerializer(serializers.ModelSerializer):
    schedule = EventScheduleReadSerializer(source="eventschedule", read_only=True)
    equipments = serializers.SerializerMethodField()
    assignment = serializers.CharField(source="assignment.emp_name", read_only=True)
    department = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "event_name",
            "description",
            "department",
            "assignment",
            "schedule",
            "equipments",
            "created_at"
        ]

    def get_equipments(self, obj):
        return list(
            obj.eventequipment_set
               .select_related("equipment")
               .values("equipment__id", "equipment__equipment_name")
        )





# =========================
# Event Schedule Serializer
# =========================
class EventScheduleCreateSerializer(serializers.Serializer):
    type = serializers.IntegerField()
    from_time = serializers.DateTimeField()
    to_time = serializers.DateTimeField()

    one_time_date = serializers.DateTimeField(required=False, allow_null=True)
    start_date = serializers.DateTimeField(required=False, allow_null=True)
    end_date = serializers.DateTimeField(required=False, allow_null=True)

    months = serializers.JSONField(required=False, allow_null=True)
    days = serializers.JSONField(required=False, allow_null=True)
    recurring_duration = serializers.IntegerField(required=False, allow_null=True)


# =========================
# Event Create Serializer
# =========================
class EventCreateSerializer(serializers.Serializer):
    department_id = serializers.IntegerField()

    assignment_id = serializers.IntegerField(
        required=False,
        allow_null=True
    )

    event_name = serializers.CharField(max_length=200)
    description = serializers.CharField()

    equipment_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )

    schedule = EventScheduleCreateSerializer()

    # =====================================================
    # VALIDATION
    # =====================================================
    def validate(self, attrs):
        request = self.context.get("request")
        if not request:
            raise serializers.ValidationError(
                {"request": "Request context missing"}
            )

        # ---------- Get Department ----------
        try:
            department = Department.objects.select_related("clinic").get(
                id=attrs["department_id"]
            )
        except Department.DoesNotExist:
            raise serializers.ValidationError(
                {"department_id": "Invalid department_id"}
            )

        # ---------- Resolve Assignment ----------
        assignment_id = attrs.get("assignment_id")

        if assignment_id:
            try:
                assignment = Employee.objects.select_related(
                    "clinic", "dep"
                ).get(id=assignment_id)
            except Employee.DoesNotExist:
                raise serializers.ValidationError(
                    {"assignment_id": "Invalid assignment_id"}
                )
        else:
            if not hasattr(request.user, "employee"):
                raise serializers.ValidationError({
                    "assignment": "Employee profile not configured for logged-in user"
                })
            assignment = request.user.employee

        # ---------- VALIDATION 1: Clinic Match ----------
        if assignment.clinic_id != department.clinic_id:
            raise serializers.ValidationError({
                "assignment": (
                    "Employee does not belong to the same clinic "
                    "as the selected department"
                )
            })

        # ---------- VALIDATION 2: Department Match ----------
        if assignment.dep_id != department.id:
            raise serializers.ValidationError({
                "assignment": (
                    "Employee does not belong to the selected department"
                )
            })

        # ---------- VALIDATION 3: Equipments ----------
        equipment_ids = attrs.get("equipment_ids", [])

        if equipment_ids:
            equipments = Equipments.objects.filter(
                id__in=equipment_ids,
                dep=department,
                is_active=True,
                is_deleted=False
            )

            if equipments.count() != len(set(equipment_ids)):
                raise serializers.ValidationError({
                    "equipment_ids": (
                        
                        "Some equipments do not belong to this department"
                    )
                })

            attrs["validated_equipments"] = equipments

        # Inject resolved objects for create()
        attrs["department_obj"] = department
        attrs["assignment_obj"] = assignment

        return attrs

    # =====================================================
    # CREATE
    # =====================================================
    @transaction.atomic
    def create(self, validated_data):
        department = validated_data.pop("department_obj")
        assignment = validated_data.pop("assignment_obj")
        equipments = validated_data.pop("validated_equipments", [])
        schedule_data = validated_data.pop("schedule")

        # ---------- Create Event ----------
        event = Event.objects.create(
            department=department,
            assignment=assignment,
            event_name=validated_data["event_name"],
            description=validated_data["description"]
        )

        # ---------- Create Schedule ----------
        EventSchedule.objects.create(
            event=event,
            type=schedule_data["type"],
            from_time=schedule_data["from_time"],
            to_time=schedule_data["to_time"],
            one_time_date=schedule_data.get("one_time_date"),
            start_date=schedule_data.get("start_date"),
            end_date=schedule_data.get("end_date"),
            months=schedule_data.get("months"),
            days=schedule_data.get("days"),
            recurring_duration=schedule_data.get("recurring_duration"),
        )

        # ---------- Link Equipments ----------
        for equipment in equipments:
            EventEquipment.objects.create(
                event=event,
                equipment=equipment
            )

        return event




# =========================
# SubTask Serializer
# =========================
class SubTaskSerializer(serializers.ModelSerializer):
    # Map frontend field → model field
    sub_task_due_date = serializers.DateTimeField(source="due_date")

    class Meta:
        model = SubTask
        fields = [
            "sub_task_due_date",
            "description",
            "status"
        ]



# =========================
# Document Serializer
# =========================
class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "document_name",
            "data"
        ]



# =========================
# Task Serializer
# =========================
class TaskSerializer(serializers.ModelSerializer):
    sub_tasks = SubTaskSerializer(many=True, required=False)
    documents = DocumentSerializer(many=True, required=False)

    assignment = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Task
        fields = [
            "event",
            "assignment",
            "due_date",
            "description",
            "status",
            "sub_tasks",
            "documents"
        ]

    # ==================================================
    # VALIDATION
    # ==================================================
    def validate(self, attrs):
        request = self.context.get("request")

        if not request or not hasattr(request.user, "employee"):
            raise serializers.ValidationError("Employee profile not found")

        employee = request.user.employee
        event = attrs.get("event")

        # ❌ Assignment must NEVER come from frontend
        if "assignment" in self.initial_data:
            raise serializers.ValidationError({
                "assignment": "Assignment is automatically set to logged-in user"
            })

        # =========================
        # UPDATE
        # =========================
        if self.instance:
            #  Only task assignee can update
            if self.instance.assignment_id != employee.id:
                raise serializers.ValidationError({
                    "assignment": "Only task assignee can update this task"
                })

            #  Event change allowed BUT must be same clinic
            if event:
                if event.department.clinic_id != employee.clinic_id:
                    raise serializers.ValidationError({
                        "event": "You cannot move task to another clinic's event"
                    })

            return attrs

        # =========================
        # CREATE
        # =========================
        if event.department.clinic_id != employee.clinic_id:
            raise serializers.ValidationError({
                "event": "You cannot create tasks for another clinic"
            })

        return attrs

    # ==================================================
    # CREATE
    # ==================================================
    @transaction.atomic
    def create(self, validated_data):
        sub_tasks_data = validated_data.pop("sub_tasks", [])
        documents_data = validated_data.pop("documents", [])

        employee = self.context["request"].user.employee

        task = Task.objects.create(
            assignment=employee,
            **validated_data
        )

        SubTask.objects.bulk_create([
            SubTask(
                task=task,
                assignment=employee,
                **sub_task
            )
            for sub_task in sub_tasks_data
        ])

        Document.objects.bulk_create([
            Document(
                task=task,
                **doc
            )
            for doc in documents_data
        ])

        return task

    # ==================================================
    # UPDATE
    # ==================================================
    @transaction.atomic
    def update(self, instance, validated_data):
        # 🔒 Assignment is IMMUTABLE
        validated_data.pop("assignment", None)

        sub_tasks_data = validated_data.pop("sub_tasks", None)
        documents_data = validated_data.pop("documents", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if sub_tasks_data is not None:
            instance.subtask_set.all().delete()
            SubTask.objects.bulk_create([
                SubTask(
                    task=instance,
                    assignment=instance.assignment,
                    **sub_task
                )
                for sub_task in sub_tasks_data
            ])

        if documents_data is not None:
            instance.document_set.all().delete()
            Document.objects.bulk_create([
                Document(
                    task=instance,
                    **doc
                )
                for doc in documents_data
            ])

        return instance
    
 # =========================
  # Employee Create Serializer
  # =========================
class EmployeeCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    clinic_id = serializers.IntegerField()
    department_id = serializers.IntegerField()
    emp_type = serializers.CharField(max_length=100)
    emp_name = serializers.CharField(max_length=200)

    def create(self, validated_data):
        try:
            user = User.objects.get(id=validated_data["user_id"])
        except User.DoesNotExist:
            raise serializers.ValidationError({"user_id": "Invalid user_id"})

        try:
            clinic = Clinic.objects.get(id=validated_data["clinic_id"])
        except Clinic.DoesNotExist:
            raise serializers.ValidationError({"clinic_id": "Invalid clinic_id"})

        try:
            department = Department.objects.get(id=validated_data["department_id"])
        except Department.DoesNotExist:
            raise serializers.ValidationError({"department_id": "Invalid department_id"})

        # ❗ prevent duplicate employee for same user
        if Employee.objects.filter(user=user).exists():
            raise serializers.ValidationError({
                "user_id": "Employee already exists for this user"
            })

        employee = Employee.objects.create(
            user=user,
            clinic=clinic,
            dep=department,
            emp_type=validated_data["emp_type"],
            emp_name=validated_data["emp_name"]
        )

        return employee
    
  # =========================
  # User Create Serializer
  # =========================
   
from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["username", "password"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
