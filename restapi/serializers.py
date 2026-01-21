from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import (
    Clinic,
    Department,
    Equipments,
    EquipmentDetails,
    Parameters,
    ParameterValues,
    Event,
    EventSchedule,
    EventEquipment,
    EventParameter,
    Employee,
    Task,
    SubTask,
    Document,
    Task_Event,
    Environment,
    Environment_Parameter,
    Environment_Parameter_Value,
)


from rest_framework import serializers
from .models import (
    EquipmentDetails,
    Parameters,
    ParameterValues,
    SubTask,
    Document,
    Task,
)

# =====================================================
# Equipment Details Serializer
# =====================================================
class EquipmentDetailSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = EquipmentDetails
        fields = [
            "id",              # ✅ MUST BE HERE
            "equipment_num",
            "make",
            "model",
            "is_active",
        ]



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
# SubTask Serializer
# =====================================================
class SubTaskSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = SubTask
        fields = [
            "id",
            "due_date",
            "name",     # ✅ payload must send name
            "status",
        ]


# =====================================================
# Document Serializer
# =====================================================
class DocumentSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = Document
        fields = [
            "id",
            "document_name",
            "data",
        ]


# =====================================================
# Task WRITE Serializer
# =====================================================
class TaskSerializer(serializers.ModelSerializer):
    sub_tasks = SubTaskSerializer(many=True, required=False)
    documents = DocumentSerializer(many=True, required=False)

    task_event = serializers.PrimaryKeyRelatedField(
        queryset=Task_Event.objects.all()
    )

    assignment = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all()
    )

    class Meta:
        model = Task
        fields = [
            # ✅ FIXED
            "task_event",

            "assignment",
            "name",
            "due_date",
            "description",
            "status",

            # ⏱️ READ ONLY
            "timer_status",
            "total_tracked_sec",
            "timer_started_at",

            "sub_tasks",
            "documents",
        ]

        read_only_fields = [
            "timer_status",
            "total_tracked_sec",
            "timer_started_at",
        ]





# =====================================================
# Parameter Value Create Serializer
# =====================================================
class ParameterValueCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParameterValues
        fields = [
            "id",
            
            "parameter",
            "equipment_details",
            "content",
        ]




# =====================================================
# Equipment Serializer
# =====================================================
# This serializer is responsible for:
# - Creating equipment
# - Updating equipment
# - Handling equipment active/inactive state
# - Managing nested equipment details and parameters
class EquipmentSerializer(serializers.ModelSerializer):
    # 🔑 equipment_name OPTIONAL for PUT
    equipment_name = serializers.CharField(required=False)

    equipment_details = EquipmentDetailSerializer(many=True, required=False)
    parameters = ParameterSerializer(many=True, required=False)

    class Meta:
        model = Equipments
        fields = [
            "id",
            "equipment_name",
            "is_active",
            "equipment_details",
            "parameters",
        ]

    # ==================================================
    # CREATE (POST)
    # ==================================================
    @transaction.atomic
    def create(self, validated_data):
        equipment_details_data = validated_data.pop("equipment_details", [])
        parameters_data = validated_data.pop("parameters", [])
        department = validated_data.pop("dep")

        equipment = Equipments.objects.create(
            dep=department,
            **validated_data
        )

        for detail in equipment_details_data:
            EquipmentDetails.objects.create(
                equipment=equipment,
                **detail
            )

        for param in parameters_data:
            Parameters.objects.create(
                equipment=equipment,
                parameter_name=param["parameter_name"],
                is_active=param.get("is_active", True),
                config=param.get("config"),
            )

        equipment.refresh_from_db()
        return equipment

    # ==================================================
    # UPDATE (PUT ONLY – CONTROLLED)
    # ==================================================
    @transaction.atomic
    def update(self, instance, validated_data):
        equipment_details_data = validated_data.pop("equipment_details", [])
        parameters_data = validated_data.pop("parameters", [])

        # ----------------------------
        # Update Equipment (ONLY IF SENT)
        # ----------------------------
        if "equipment_name" in validated_data:
            instance.equipment_name = validated_data["equipment_name"]

        if "is_active" in validated_data:
            instance.is_active = validated_data["is_active"]

        instance.save()

        # ==================================================
        # EquipmentDetails (STRICT)
        # ==================================================
        for detail in equipment_details_data:
            detail_id = detail.get("id")

            if detail_id is not None:
                try:
                    detail_instance = EquipmentDetails.objects.get(
                        id=detail_id,
                        equipment=instance
                    )
                except EquipmentDetails.DoesNotExist:
                    raise ValidationError(
                        f"Invalid equipment_details id {detail_id} for this equipment"
                    )

                for field, value in detail.items():
                    if field != "id":
                        setattr(detail_instance, field, value)

                detail_instance.save()

            else:
                EquipmentDetails.objects.create(
                    equipment=instance,
                    **detail
                )

        # ==================================================
        # Parameters (STRICT)
        # ==================================================
        for param in parameters_data:
            param_id = param.get("id")

            if param_id is not None:
                try:
                    param_instance = Parameters.objects.get(
                        id=param_id,
                        equipment=instance
                    )
                except Parameters.DoesNotExist:
                    raise ValidationError(
                        f"Invalid parameter id {param_id} for this equipment"
                    )

                param_instance.parameter_name = param.get(
                    "parameter_name",
                    param_instance.parameter_name
                )
                param_instance.is_active = param.get(
                    "is_active",
                    param_instance.is_active
                )

                if "config" in param:
                    param_instance.config = param["config"]

                param_instance.save()

            else:
                Parameters.objects.create(
                    equipment=instance,
                    parameter_name=param["parameter_name"],
                    is_active=param.get("is_active", True),
                    config=param.get("config"),
                )

        instance.refresh_from_db()
        return instance


# =====================================================
# Department Serializer
# =====================================================
class DepartmentSerializer(serializers.ModelSerializer):
    equipments = EquipmentSerializer(many=True, required=False)

    class Meta:
        model = Department
        fields = ["id", "name", "is_active", "equipments"]

    @transaction.atomic
    def update(self, instance, validated_data):
        # equipments_data → list of equipment dictionaries sent from FE
        equipments_data = validated_data.pop("equipments", [])

        # Update department fields
        instance.name = validated_data.get("name", instance.name)
        instance.is_active = validated_data.get(
            "is_active", instance.is_active
        )
        instance.save()

        # ----------------------------------------------
        # Equipment Updates (Clinic / Department level)
        # ----------------------------------------------
        for equipment_data in equipments_data:

            # equipment_id → primary key of equipment
            equipment_id = equipment_data.get("id")
            if not equipment_id:
                raise serializers.ValidationError(
                    "Equipment ID is required for clinic-level update"
                )

            # Fetch equipment belonging to this department
            equipment_instance = Equipments.objects.get(
                id=equipment_id,
                dep=instance
            )

            # Use replace_mode=True to fully overwrite parameter config
            equipment_serializer = EquipmentSerializer(
                instance=equipment_instance,
                data=equipment_data,
                replace_mode=True
            )

            equipment_serializer.is_valid(raise_exception=True)
            equipment_serializer.save()

        return instance




# =====================================================
# Clinic Serializer
# =====================================================
class ClinicSerializer(serializers.ModelSerializer):
    # department → list of departments with nested equipments
    department = serializers.ListField(required=False)

    class Meta:
        model = Clinic
        fields = ["id", "name", "department"]

    # =========================
    # CREATE CLINIC
    # =========================
    @transaction.atomic
    def create(self, validated_data):
        # Extract departments data from request payload
        departments_data = validated_data.pop("department", [])

        # Create clinic record
        clinic = Clinic.objects.create(**validated_data)

        # Loop through each department sent in payload
        for department_data in departments_data:

            # Create department under this clinic
            department_instance = Department.objects.create(
                clinic=clinic,
                name=department_data["name"],
                is_active=department_data.get("is_active", True),
            )

            # Create equipments under the department
            for equipment_data in department_data.get("equipments", []):
                self._create_equipment(
                    equipment_data,
                    department_instance
                )

        return clinic

    # =========================
    # UPDATE CLINIC
    # =========================
    @transaction.atomic
    def update(self, instance, validated_data):
        # Extract departments data from request payload
        departments_data = validated_data.pop("department", [])

        # Update clinic name if provided
        instance.name = validated_data.get("name", instance.name)
        instance.save()

        # Loop through departments sent in payload
        for department_data in departments_data:
            department_id = department_data.get("id")

            if department_id:
                # Update existing department
                department_instance = Department.objects.get(
                    id=department_id,
                    clinic=instance
                )
                department_instance.name = department_data.get(
                    "name", department_instance.name
                )
                department_instance.is_active = department_data.get(
                    "is_active", department_instance.is_active
                )
                department_instance.save()
            else:
                # Create new department if ID not provided
                department_instance = Department.objects.create(
                    clinic=instance,
                    name=department_data["name"],
                    is_active=department_data.get("is_active", True),
                )

            # Update or create equipments under this department
            for equipment_data in department_data.get("equipments", []):
                self._update_or_create_equipment(
                    equipment_data,
                    department_instance
                )

        return instance

    # =========================
    # HELPER: CREATE EQUIPMENT
    # =========================
    def _create_equipment(self, equipment_data, department_instance):
        # Create equipment under given department
        equipment_instance = Equipments.objects.create(
            dep=department_instance,
            equipment_name=equipment_data["equipment_name"],
            is_active=equipment_data.get("is_active", True),
        )

        # Create equipment details (like model, make, number)
        for equipment_detail_data in equipment_data.get(
            "equipment_details", []
        ):
            EquipmentDetails.objects.create(
                equipment=equipment_instance,
                **equipment_detail_data
            )

        # Create parameters for the equipment
        for parameter_data in equipment_data.get("parameters", []):
            Parameters.objects.create(
                equipment=equipment_instance,
                parameter_name=parameter_data["parameter_name"],
                is_active=parameter_data.get("is_active", True),
                config=parameter_data.get("config"),
            )

    # =========================
    # UPDATE OR CREATE EQUIPMENT
    # =========================
    def _update_or_create_equipment(
        self,
        equipment_data,
        department_instance
    ):
        equipment_id = equipment_data.get("id")

        if equipment_id:
            # Update existing equipment
            equipment_instance = Equipments.objects.get(
                id=equipment_id,
                dep=department_instance
            )
            equipment_instance.equipment_name = equipment_data.get(
                "equipment_name",
                equipment_instance.equipment_name
            )
            equipment_instance.is_active = equipment_data.get(
                "is_active",
                equipment_instance.is_active
            )
            equipment_instance.save()
        else:
            # Create new equipment if ID not provided
            equipment_instance = Equipments.objects.create(
                dep=department_instance,
                equipment_name=equipment_data["equipment_name"],
                is_active=equipment_data.get("is_active", True),
            )

        # -------------------------
        # Equipment Details Update
        # -------------------------
        for equipment_detail_data in equipment_data.get(
            "equipment_details", []
        ):
            equipment_detail_id = equipment_detail_data.get("id")

            if equipment_detail_id:
                # Update existing equipment detail
                equipment_detail_instance = EquipmentDetails.objects.get(
                    id=equipment_detail_id,
                    equipment=equipment_instance
                )

                for field_name, field_value in equipment_detail_data.items():
                    if field_name != "id":
                        setattr(
                            equipment_detail_instance,
                            field_name,
                            field_value
                        )

                equipment_detail_instance.save()
            else:
                # Create new equipment detail
                EquipmentDetails.objects.create(
                    equipment=equipment_instance,
                    **equipment_detail_data
                )

        # -------------------------
        # Parameters Update
        # -------------------------
        for parameter_data in equipment_data.get("parameters", []):
            parameter_id = parameter_data.get("id")

            if parameter_id:
                # Update existing parameter
                parameter_instance = Parameters.objects.get(
                    id=parameter_id,
                    equipment=equipment_instance
                )
                parameter_instance.parameter_name = parameter_data.get(
                    "parameter_name",
                    parameter_instance.parameter_name
                )
                parameter_instance.is_active = parameter_data.get(
                    "is_active",
                    parameter_instance.is_active
                )
                parameter_instance.config = parameter_data.get(
                    "config",
                    parameter_instance.config
                )
                parameter_instance.save()
            else:
                # Create new parameter
                Parameters.objects.create(
                    equipment=equipment_instance,
                    parameter_name=parameter_data["parameter_name"],
                    is_active=parameter_data.get("is_active", True),
                    config=parameter_data.get("config"),
                )



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
        try:
            parameter = Parameters.objects.get(
                id=attrs["parameter_id"],
                is_deleted=False
            )
        except Parameters.DoesNotExist:
            raise ValidationError("Invalid or already deleted parameter")

        attrs["parameter"] = parameter
        return attrs

    def save(self):
        parameter = self.validated_data["parameter"]

        parameter.is_deleted = True
        parameter.is_active = False
        parameter.deleted_at = timezone.now()

        parameter.save(
            update_fields=["is_deleted", "is_active", "deleted_at"]
        )

        return parameter



# =====================================================
# READ SERIALIZERS
# =====================================================
class EquipmentDetailReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentDetails
        fields = ['id', 'equipment_num', 'make', 'model', 'is_active']

class ParameterValueReadSerializer(serializers.ModelSerializer):
    equipment_details_id = serializers.IntegerField(
        source="equipment_details.id",
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


   
class EquipmentReadSerializer(serializers.ModelSerializer):
    equipment_details = EquipmentDetailReadSerializer(
        many=True,
        source="equipmentdetails_set"
    )
    parameters = ParameterReadSerializer(many=True)

    class Meta:
        model = Equipments
        fields = [
            "id",
            "equipment_name",
            "is_active",
            "created_at", 
            "equipment_details",
            "parameters",
        ]



class DepartmentReadSerializer(serializers.ModelSerializer):
    equipments = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = ['id', 'name', 'is_active', 'equipments']

    def get_equipments(self, obj):
        qs = (
            obj.equipments_set
            .filter(is_deleted=False)
            .prefetch_related(
                "equipmentdetails_set",
                "parameters",
          
            )
        )
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
            "recurring_duration",
        ]

class SubTaskReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubTask
        fields = [
            "id",
            "assignment",
            "due_date",
            "name",
            "status",
            "created_at",
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

    # ✅ Derived event (READ ONLY)
    event = serializers.IntegerField(
        source="task_event.event.id",
        read_only=True
    )

    task_event = serializers.IntegerField(
        source="task_event.id",
        read_only=True
    )

    class Meta:
        model = Task
        fields = [
            "id",

            # ✅ FIXED
            "event",
            "task_event",

            "assignment",
            "name",
            "description",
            "due_date",
            "status",

            # ⏱️ TASK TIMER FIELDS
            "timer_status",
            "total_tracked_sec",
            "timer_started_at",

            "sub_tasks",
            "documents",
            "created_at",
            "modified_at",
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
    schedule = serializers.SerializerMethodField()
    equipments = serializers.SerializerMethodField()
    parameters = serializers.SerializerMethodField()

    assignment = serializers.CharField(
        source="assignment.emp_name",
        read_only=True
    )
    department = serializers.CharField(
        source="department.name",
        read_only=True
    )

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
            "parameters",
            "created_at",
        ]

    def get_schedule(self, event_instance):
        schedule = (
            event_instance.eventschedule_set
            .order_by("-created_at")
            .first()
        )
        if not schedule:
            return None
        return EventScheduleReadSerializer(schedule).data

    def get_equipments(self, event_instance):
        return list(
            event_instance.eventequipment_set
            .select_related("equipment_details__equipment")
            .values(
                "equipment_details__id",
                "equipment_details__equipment_num",
                "equipment_details__equipment__id",
                "equipment_details__equipment__equipment_name",
            )
        )

    def get_parameters(self, event_instance):
        return list(
            event_instance.eventparameter_set
            .select_related("parameter")
            .values(
                "parameter__id",
                "parameter__parameter_name",
            )
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
            "environment_parameter_id",
        ]

class DepartmentWithEnvironmentReadSerializer(serializers.ModelSerializer):
    equipments = serializers.SerializerMethodField()
    environments = serializers.SerializerMethodField()  # ✅ CHANGED

    class Meta:
        model = Department
        fields = [
            "id",
            "name",
            "is_active",
            "equipments",
            "environments",   # ✅ CHANGED
        ]

    def get_equipments(self, obj):
        qs = (
            obj.equipments_set
            .filter(is_deleted=False)
            .prefetch_related(
                "equipmentdetails_set",
                "parameters"
            )
        )
        return EquipmentReadSerializer(qs, many=True).data

    def get_environments(self, obj):
        environments = (
            Environment.objects
            .filter(
                dep=obj,
                is_deleted=False
            )
            .order_by("-created_at")        # latest first
            .prefetch_related("parameters")
        )

        return EnvironmentReadSerializer(environments, many=True).data

class ClinicFullHierarchyReadSerializer(serializers.ModelSerializer):
    department = serializers.SerializerMethodField()

    class Meta:
        model = Clinic
        fields = [
            "id",
            "name",
            "department",
        ]

    def get_department(self, obj):
        departments = (
            obj.department_set
            .filter(is_active=True)
            .prefetch_related(
                "equipments_set__equipmentdetails_set",
                "equipments_set__parameters",
                "environments__parameters",
            )
        )

        return DepartmentWithEnvironmentReadSerializer(
            departments, many=True
        ).data



# =========================
# Event Create Serializer
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
    assignment_id = serializers.IntegerField(required=False, allow_null=True)
    event_name = serializers.CharField()
    description = serializers.CharField()

    # ✅ CHANGED
    equipment_details_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )

    parameter_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )

    schedule = EventScheduleCreateSerializer()

    # ---------------- VALIDATION ----------------
    def validate(self, attrs):
        # Department
        department = Department.objects.get(id=attrs["department_id"])

        # Assignment
        assignment = (
            Employee.objects.get(id=attrs["assignment_id"])
            if attrs.get("assignment_id")
            else self.context["request"].user.employee
        )

        equipment_details_ids = attrs.get("equipment_details_ids", [])
        parameter_ids = attrs.get("parameter_ids", [])

        # =========================
        # VALIDATE EQUIPMENT DETAILS
        # =========================
        equipment_details = EquipmentDetails.objects.filter(
            id__in=equipment_details_ids,
            equipment__dep=department,
            is_active=True
        )

        if equipment_details.count() != len(set(equipment_details_ids)):
            raise ValidationError("Invalid equipment details selection")

        # =========================
        # DERIVE EQUIPMENTS (MASTER)
        # =========================
        equipments = Equipments.objects.filter(
            id__in=equipment_details.values_list("equipment_id", flat=True),
            is_active=True,
            is_deleted=False
        )

        # =========================
        # VALIDATE PARAMETERS
        # =========================
        parameters = Parameters.objects.filter(
            id__in=parameter_ids,
            is_active=True
        )

        invalid = parameters.exclude(equipment__in=equipments)
        if invalid.exists():
            raise ValidationError(
                "Parameters must belong to selected equipments"
            )

        # Store validated objects
        attrs["department"] = department
        attrs["assignment"] = assignment
        attrs["equipment_details"] = equipment_details
        attrs["parameters"] = parameters

        return attrs

    # ---------------- CREATE ----------------
    @transaction.atomic
    def create(self, validated_data):
        event = Event.objects.create(
            department=validated_data["department"],
            assignment=validated_data["assignment"],
            event_name=validated_data["event_name"],
            description=validated_data["description"]
        )

        # Create schedule
        EventSchedule.objects.create(
            event=event,
            **validated_data["schedule"]
        )

        # Link equipment details
        for ed in validated_data["equipment_details"]:
            EventEquipment.objects.create(
                event=event,
                equipment_details=ed
            )

        # Link parameters
        for p in validated_data["parameters"]:
            EventParameter.objects.create(
                event=event,
                parameter=p
            )

        return event




# =========================
# SubTask Serializer
# =========================
class SubTaskSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = SubTask
        fields = [
            "id",
            "due_date",
            "name",     # payload MUST send name
            "status",
        ]


# =========================
# Document Serializer
# =========================
class DocumentSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = Document
        fields = [
            "id",
            "document_name",
            "data",
        ]
        extra_kwargs = {
            "data": {"required": False}  # optional on update
        }


# =========================
# Task Serializer
# =========================
class TaskSerializer(serializers.ModelSerializer):
    sub_tasks = SubTaskSerializer(many=True, required=False)
    documents = DocumentSerializer(many=True, required=False)

    task_event = serializers.PrimaryKeyRelatedField(
        queryset=Task_Event.objects.all()
    )

    assignment = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all()
    )

    class Meta:
        model = Task
        fields = [
            "task_event",     # ✅ FIXED
            "assignment",
            "name",
            "due_date",
            "description",
            "status",
            "sub_tasks",
            "documents",
        ]

    # =========================
    # CREATE
    # =========================
    @transaction.atomic
    def create(self, validated_data):
        sub_tasks_data = validated_data.pop("sub_tasks", [])
        documents_data = validated_data.pop("documents", [])

        task_instance = Task.objects.create(**validated_data)

        # Create sub-tasks
        for sub_task_data in sub_tasks_data:
            SubTask.objects.create(
                task=task_instance,
                assignment=task_instance.assignment,
                **sub_task_data
            )

        # Create documents
        for document_data in documents_data:
            Document.objects.create(
                task=task_instance,
                **document_data
            )

        return task_instance

    # =========================
    # UPDATE (ID SAFE)
    # =========================
    @transaction.atomic
    def update(self, instance, validated_data):
        validated_data.pop("assignment", None)
        validated_data.pop("task_event", None)  # ❗ optional: prevent reassignment

        sub_tasks_data = validated_data.pop("sub_tasks", [])
        documents_data = validated_data.pop("documents", [])

        # ---- update task fields ----
        for field_name, field_value in validated_data.items():
            setattr(instance, field_name, field_value)
        instance.save()

        # =========================
        # SUB TASKS
        # =========================
        existing_subtasks = {
            subtask.id: subtask
            for subtask in instance.subtask_set.all()
        }

        received_subtask_ids = []

        for sub_task_data in sub_tasks_data:
            sub_task_id = sub_task_data.get("id")

            if sub_task_id:
                sub_task_instance = existing_subtasks.get(sub_task_id)
                if not sub_task_instance:
                    raise serializers.ValidationError({
                        "sub_tasks": f"SubTask {sub_task_id} does not belong to this task"
                    })

                sub_task_instance.due_date = sub_task_data["due_date"]
                sub_task_instance.name = sub_task_data["name"]
                sub_task_instance.status = sub_task_data.get(
                    "status",
                    sub_task_instance.status
                )
                sub_task_instance.save()

                received_subtask_ids.append(sub_task_id)
            else:
                new_subtask = SubTask.objects.create(
                    task=instance,
                    assignment=instance.assignment,
                    **sub_task_data
                )
                received_subtask_ids.append(new_subtask.id)

        for subtask_id, subtask in existing_subtasks.items():
            if subtask_id not in received_subtask_ids:
                subtask.delete()

        # =========================
        # DOCUMENTS
        # =========================
        existing_documents = {
            doc.id: doc
            for doc in instance.document_set.all()
        }

        received_document_ids = []

        for document_data in documents_data:
            document_id = document_data.get("id")

            if document_id:
                document_instance = existing_documents.get(document_id)
                if not document_instance:
                    raise serializers.ValidationError({
                        "documents": f"Document {document_id} does not belong to this task"
                    })

                document_instance.document_name = document_data.get(
                    "document_name",
                    document_instance.document_name
                )

                if "data" in document_data:
                    document_instance.data = document_data["data"]

                document_instance.save()
                received_document_ids.append(document_id)
            else:
                new_document = Document.objects.create(
                    task=instance,
                    **document_data
                )
                received_document_ids.append(new_document.id)

        for doc_id, document in existing_documents.items():
            if doc_id not in received_document_ids:
                document.delete()

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

# =========================
# Task Activate Serializer
# =========================
class TaskActivateSerializer(serializers.Serializer):
    task_id = serializers.IntegerField()

    def validate(self, attrs):
        try:
            task = Task.objects.get(id=attrs["task_id"])
        except Task.DoesNotExist:
            raise ValidationError("Invalid task id")

        attrs["task"] = task
        return attrs

    def save(self):
        task = self.validated_data["task"]

        # assuming inactive task uses status
        task.status = "active"
        task.save(update_fields=["status"])
        return task
    
# =========================
# Equipment Activate Serializer
# =========================
class EquipmentActivateSerializer(serializers.Serializer):
    equipment_id = serializers.IntegerField()

    def validate(self, attrs):
        try:
            equipment = Equipments.objects.get(
                id=attrs["equipment_id"],
                is_deleted=False
            )
        except Equipments.DoesNotExist:
            raise ValidationError("Invalid equipment id")

        attrs["equipment"] = equipment
        return attrs

    def save(self):
        equipment = self.validated_data["equipment"]
        equipment.is_active = True
        equipment.save(update_fields=["is_active"])
        return equipment

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
    @transaction.atomic
    def create(self, validated_data):
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
    def update(self, instance, validated_data):
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
    
# =========================
# WRITE Serializer
# =========================
class TaskEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task_Event
        fields = [
            "id",
            "name",
            "dep",
            "is_deleted",
            "created_at",
            "modified_at"
        ]
        read_only_fields = ("created_at", "modified_at")




# =========================
# READ Serializer (optional but recommended)
# =========================
class TaskEventReadSerializer(serializers.ModelSerializer):
    dep_name = serializers.CharField(source="dep.name", read_only=True)

    class Meta:
        model = Task_Event
        fields = [
            "id",
            "name",
            "dep",
            "dep_name",
            "is_deleted",
            "created_at",
            "modified_at"
        ]
