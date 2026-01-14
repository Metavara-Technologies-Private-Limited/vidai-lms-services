from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import (
    Clinic, Department, Equipments,
    EquipmentDetails, EventParameter, Parameters, ParameterValues, Event,
    EventSchedule,
    EventEquipment,
    Department,
    Employee,
    Equipments,
    Task,
    SubTask, 
    Document,
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
            "description",
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
# Task Serializer
# =====================================================
class TaskSerializer(serializers.ModelSerializer):
    sub_tasks = SubTaskSerializer(many=True, required=False)
    documents = DocumentSerializer(many=True, required=False)

    class Meta:
        model = Task
        fields = [
            "event",
            "assignment",
            "due_date",
            "description",
            "status",
            "sub_tasks",
            "documents",
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
    # HELPER: UPDATE OR CREATE EQUIPMENT
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
            "schedule",      # ✅ now works
            "equipments",
            "parameters",
            "created_at",
        ]

    # ✅ FIXED SCHEDULE READ
    def get_schedule(self, event_instance):
        schedule_instance = (
            event_instance.eventschedule_set
            .order_by("-created_at")
            .first()
        )

        if not schedule_instance:
            return None

        return EventScheduleReadSerializer(schedule_instance).data

    def get_equipments(self, event_instance):
        return list(
            event_instance.eventequipment_set
            .select_related("equipment")
            .values(
                "equipment__id",
                "equipment__equipment_name"
            )
        )

    def get_parameters(self, event_instance):
        return list(
            event_instance.eventparameter_set
            .select_related("parameter")
            .values(
                "parameter__id",
                "parameter__parameter_name",
                #"parameter__config"
            )
        )


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

    # List of equipment IDs selected for the event
    equipment_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False
    )

    # List of parameter IDs selected for the event
    parameter_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False
    )

    # Event scheduling information
    schedule = EventScheduleCreateSerializer()

    # ---------------- VALIDATION ----------------
    def validate(self, attrs):
        # Validate department existence
        department = Department.objects.get(id=attrs["department_id"])

        # Validate assignment (employee)
        assignment = (
            Employee.objects.get(id=attrs["assignment_id"])
            if attrs.get("assignment_id")
            else self.context["request"].user.employee
        )

        equipment_ids = attrs.get("equipment_ids", [])
        parameter_ids = attrs.get("parameter_ids", [])

        # ACTIVE / INACTIVE VALIDATION:
        # Only active, non-deleted equipment can be linked to event
        equipments = Equipments.objects.filter(
            id__in=equipment_ids,
            dep=department,
            is_active=True,      #  inactive equipment blocked here
            is_deleted=False
        )

        if equipments.count() != len(set(equipment_ids)):
            raise ValidationError("Invalid equipment selection")

        # Only active parameters are allowed
        parameters = Parameters.objects.filter(
            id__in=parameter_ids,
            is_active=True
        )

        # Ensure parameters belong to selected equipment
        invalid = parameters.exclude(equipment__in=equipments)
        if invalid.exists():
            raise ValidationError(
                "Parameters must belong to selected equipments"
            )

        # Store validated objects for create()
        attrs["department"] = department
        attrs["assignment"] = assignment
        attrs["equipments"] = equipments
        attrs["parameters"] = parameters
        return attrs

    # ---------------- CREATE ----------------
    @transaction.atomic
    def create(self, validated_data):
        # Create event
        event = Event.objects.create(
            department=validated_data["department"],
            assignment=validated_data["assignment"],
            event_name=validated_data["event_name"],
            description=validated_data["description"]
        )

        # Create event schedule
        EventSchedule.objects.create(
            event=event,
            **validated_data["schedule"]
        )

        # Link equipments to event
        # eq = one equipment object
        for eq in validated_data["equipments"]:
            EventEquipment.objects.create(event=event, equipment=eq)

        # Link parameters to event
        # p = one parameter object
        for p in validated_data["parameters"]:
            EventParameter.objects.create(event=event, parameter=p)

        return event




# =========================
# SubTask Serializer
# =========================
class SubTaskSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    sub_task_due_date = serializers.DateTimeField(source="due_date")

    class Meta:
        model = SubTask
        fields = [
            "id",
            "sub_task_due_date",
            "description",
            "status"
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
            "data"
        ]
        extra_kwargs = {
            "data": {"required": False}  # data optional in UPDATE
        }



# =========================
# Task Serializer
# =========================
class TaskSerializer(serializers.ModelSerializer):
    sub_tasks = SubTaskSerializer(many=True, required=False)
    documents = DocumentSerializer(many=True, required=False)

    assignment = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all()
    )

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
        # 🔒 assignment is immutable
        validated_data.pop("assignment", None)

        sub_tasks_data = validated_data.pop("sub_tasks", [])
        documents_data = validated_data.pop("documents", [])

        # ---- update task fields ----
        for field_name, field_value in validated_data.items():
            setattr(instance, field_name, field_value)
        instance.save()

        # =================================================
        # SUB TASKS (ID SAFE)
        # =================================================
        existing_subtasks = {
            existing_subtask_instance.id: existing_subtask_instance
            for existing_subtask_instance in instance.subtask_set.all()
        }

        received_subtask_ids = []

        for sub_task_data in sub_tasks_data:
            sub_task_id = sub_task_data.get("id")

            if sub_task_id:
                # UPDATE existing sub-task
                sub_task_instance = existing_subtasks.get(sub_task_id)
                if not sub_task_instance:
                    raise serializers.ValidationError({
                        "sub_tasks": (
                            f"SubTask {sub_task_id} does not belong to this task"
                        )
                    })

                sub_task_instance.due_date = sub_task_data["due_date"]
                sub_task_instance.description = sub_task_data["description"]
                sub_task_instance.status = sub_task_data.get(
                    "status",
                    sub_task_instance.status
                )
                sub_task_instance.save()

                received_subtask_ids.append(sub_task_id)
            else:
                # CREATE new sub-task
                sub_task_instance = SubTask.objects.create(
                    task=instance,
                    assignment=instance.assignment,
                    **sub_task_data
                )
                received_subtask_ids.append(sub_task_instance.id)

        # DELETE removed sub-tasks
        for existing_subtask_id, existing_subtask_instance in (
            existing_subtasks.items()
        ):
            if existing_subtask_id not in received_subtask_ids:
                existing_subtask_instance.delete()

        # =================================================
        # DOCUMENTS (ID SAFE)
        # =================================================
        existing_documents = {
            existing_document_instance.id: existing_document_instance
            for existing_document_instance in instance.document_set.all()
        }

        received_document_ids = []

        for document_data in documents_data:
            document_id = document_data.get("id")

            if document_id:
                # UPDATE existing document
                document_instance = existing_documents.get(document_id)
                if not document_instance:
                    raise serializers.ValidationError({
                        "documents": (
                            f"Document {document_id} does not belong to this task"
                        )
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
                # CREATE new document
                document_instance = Document.objects.create(
                    task=instance,
                    document_name=document_data["document_name"],
                    data=document_data["data"]
                )
                received_document_ids.append(document_instance.id)

        # DELETE removed documents
        for existing_document_id, existing_document_instance in (
            existing_documents.items()
        ):
            if existing_document_id not in received_document_ids:
                existing_document_instance.delete()

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
