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

    # ✅ THIS WAS MISSING
    config = serializers.JSONField(required=False, allow_null=True)

    class Meta:
        model = Parameters
        fields = [
            "id",
            "parameter_name",
            "is_active",
            "config",            # ✅ MUST BE HERE
            "parameter_values",
        ]



# =====================================================
# Equipment Serializer
# =====================================================

class ParameterValueSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = ParameterValues
        fields = ["id", "content", "created_at", "is_deleted"]
        read_only_fields = ["created_at", "is_deleted"]



# =====================================================
# Parameter Serializer
# =====================================================
class ParameterSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = Parameters
        fields = [
            "id",
            "parameter_name",
            "is_active",
            "config",
        ]

class ParameterValueCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParameterValues
        fields = ["id", "parameter", "equipment_details", "content"]


# =====================================================
# Equipment Serializer
# =====================================================
class EquipmentSerializer(serializers.ModelSerializer):
    equipment_details = EquipmentDetailSerializer(many=True, required=False)
    parameters = ParameterSerializer(many=True, required=False)

    def __init__(self, *args, **kwargs):
        # 🔑 replace_mode=True  → CLINIC / DEPARTMENT PUT
        # 🔑 replace_mode=False → EQUIPMENT PUT
        self.replace_mode = kwargs.pop("replace_mode", False)
        super().__init__(*args, **kwargs)

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
        details_data = validated_data.pop("equipment_details", [])
        params_data = validated_data.pop("parameters", [])
        department = validated_data.pop("dep")

        # Create equipment
        equipment = Equipments.objects.create(
            dep=department,
            **validated_data
        )

        # Create equipment details
        for d in details_data:
            EquipmentDetails.objects.create(
                equipment=equipment,
                **d
            )

        # Create parameters (CONFIG ONLY)
        for p in params_data:
            Parameters.objects.create(
                equipment=equipment,
                parameter_name=p["parameter_name"],
                is_active=p.get("is_active", True),
                config=p.get("config"),
            )

        return equipment

    # ==================================================
    # UPDATE (PUT)
    # ==================================================
    @transaction.atomic
    def update(self, instance, validated_data):
        details_data = validated_data.pop("equipment_details", [])
        params_data = validated_data.pop("parameters", [])

        # Update equipment fields
        instance.equipment_name = validated_data.get(
            "equipment_name", instance.equipment_name
        )
        instance.is_active = validated_data.get(
            "is_active", instance.is_active
        )
        instance.save()

        # ----------------------------------------------
        # Equipment Details
        # ----------------------------------------------
        for d in details_data:
            d_id = d.get("id")
            if d_id:
                ed = EquipmentDetails.objects.get(
                    id=d_id,
                    equipment=instance
                )
                for k, v in d.items():
                    if k != "id":
                        setattr(ed, k, v)
                ed.save()
            else:
                EquipmentDetails.objects.create(
                    equipment=instance,
                    **d
                )

        # ----------------------------------------------
        # Parameters
        # ----------------------------------------------
        for p in params_data:
            p_id = p.get("id")
            if not p_id:
                raise ValidationError("Parameter ID is required")

            parameter = Parameters.objects.get(
                id=p_id,
                equipment=instance
            )

            # ==========================================
            # CLINIC / DEPARTMENT PUT → REPLACE
            # ==========================================
            if self.replace_mode:
                if "config" in p:
                    parameter.config = p["config"]

            # ==========================================
            # EQUIPMENT PUT → ADD (HISTORY)
            # ==========================================
            else:
                if "config" in p:
                    existing_config = parameter.config or {}

                    # Normalize to history once
                    if isinstance(existing_config, dict) and "history" in existing_config:
                        history = existing_config["history"]
                    else:
                        history = []
                        if existing_config:
                            history.append({
                                **existing_config,
                                "updated_at": timezone.now().isoformat(),
                            })

                    # Append new config
                    history.append({
                        **p["config"],
                        "updated_at": timezone.now().isoformat(),
                    })

                    parameter.config = {"history": history}

            # Common fields
            parameter.parameter_name = p.get(
                "parameter_name", parameter.parameter_name
            )
            parameter.is_active = p.get(
                "is_active", parameter.is_active
            )
            parameter.save()

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
    def update(self, instance, validated_data):
        equipments_data = validated_data.pop("equipments", [])

        instance.name = validated_data.get("name", instance.name)
        instance.is_active = validated_data.get("is_active", instance.is_active)
        instance.save()

        for eq in equipments_data:
            eq_id = eq.get("id")
            if not eq_id:
                raise serializers.ValidationError(
                    "Equipment ID is required for clinic-level update"
                )

            equipment = Equipments.objects.get(
                id=eq_id,
                dep=instance
            )

            serializer = EquipmentSerializer(
                instance=equipment,
                data=eq,
                replace_mode=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

        return instance




# =====================================================
# Clinic Serializer
# =====================================================
class ClinicSerializer(serializers.ModelSerializer):
    department = serializers.ListField(required=False)

    class Meta:
        model = Clinic
        fields = ["id", "name", "department"]

    # =========================
    # CREATE
    # =========================
    @transaction.atomic
    def create(self, validated_data):
        departments_data = validated_data.pop("department", [])
        clinic = Clinic.objects.create(**validated_data)

        for dep in departments_data:
            department = Department.objects.create(
                clinic=clinic,
                name=dep["name"],
                is_active=dep.get("is_active", True),
            )

            for eq in dep.get("equipments", []):
                self._create_equipment(eq, department)

        return clinic

    # =========================
    # UPDATE
    # =========================
    @transaction.atomic
    def update(self, instance, validated_data):
        departments_data = validated_data.pop("department", [])

        instance.name = validated_data.get("name", instance.name)
        instance.save()

        for dep in departments_data:
            dep_id = dep.get("id")
            if dep_id:
                department = Department.objects.get(
                    id=dep_id,
                    clinic=instance
                )
                department.name = dep.get("name", department.name)
                department.is_active = dep.get(
                    "is_active", department.is_active
                )
                department.save()
            else:
                department = Department.objects.create(
                    clinic=instance,
                    name=dep["name"],
                    is_active=dep.get("is_active", True),
                )

            for eq in dep.get("equipments", []):
                self._update_or_create_equipment(eq, department)

        return instance

    # =========================
    # HELPERS
    # =========================
    def _create_equipment(self, eq, department):
        equipment = Equipments.objects.create(
            dep=department,
            equipment_name=eq["equipment_name"],
            is_active=eq.get("is_active", True),
        )

        for d in eq.get("equipment_details", []):
            EquipmentDetails.objects.create(
                equipment=equipment,
                **d
            )

        for p in eq.get("parameters", []):
            Parameters.objects.create(
                equipment=equipment,
                parameter_name=p["parameter_name"],
                is_active=p.get("is_active", True),
                config=p.get("config"),
            )

    def _update_or_create_equipment(self, eq, department):
        eq_id = eq.get("id")

        if eq_id:
            equipment = Equipments.objects.get(
                id=eq_id,
                dep=department
            )
            equipment.equipment_name = eq.get(
                "equipment_name", equipment.equipment_name
            )
            equipment.is_active = eq.get(
                "is_active", equipment.is_active
            )
            equipment.save()
        else:
            equipment = Equipments.objects.create(
                dep=department,
                equipment_name=eq["equipment_name"],
                is_active=eq.get("is_active", True),
            )

        for d in eq.get("equipment_details", []):
            d_id = d.get("id")
            if d_id:
                ed = EquipmentDetails.objects.get(
                    id=d_id,
                    equipment=equipment
                )
                for k, v in d.items():
                    if k != "id":
                        setattr(ed, k, v)
                ed.save()
            else:
                EquipmentDetails.objects.create(
                    equipment=equipment,
                    **d
                )

        for p in eq.get("parameters", []):
            p_id = p.get("id")
            if p_id:
                parameter = Parameters.objects.get(
                    id=p_id,
                    equipment=equipment
                )
                parameter.parameter_name = p.get(
                    "parameter_name", parameter.parameter_name
                )
                parameter.is_active = p.get(
                    "is_active", parameter.is_active
                )
                parameter.config = p.get(
                    "config", parameter.config
                )
                parameter.save()
            else:
                Parameters.objects.create(
                    equipment=equipment,
                    parameter_name=p["parameter_name"],
                    is_active=p.get("is_active", True),
                    config=p.get("config"),
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
        fields = ["id", "content", "created_at", "is_deleted"]

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

    # ✅ NEW
    parameter_ids = serializers.ListField(
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

        # ---------- Department ----------
        try:
            department = Department.objects.select_related("clinic").get(
                id=attrs["department_id"]
            )
        except Department.DoesNotExist:
            raise serializers.ValidationError({
                "department_id": "Invalid department_id"
            })

        # ---------- Assignment ----------
        assignment_id = attrs.get("assignment_id")

        if assignment_id:
            try:
                assignment = Employee.objects.select_related(
                    "clinic", "dep"
                ).get(id=assignment_id)
            except Employee.DoesNotExist:
                raise serializers.ValidationError({
                    "assignment_id": "Invalid assignment_id"
                })
        else:
            if not hasattr(request.user, "employee"):
                raise serializers.ValidationError({
                    "assignment": "Employee profile not configured"
                })
            assignment = request.user.employee

        # ---------- Clinic Match ----------
        if assignment.clinic_id != department.clinic_id:
            raise serializers.ValidationError({
                "assignment": "Employee does not belong to this clinic"
            })

        # ---------- Department Match ----------
        if assignment.dep_id != department.id:
            raise serializers.ValidationError({
                "assignment": "Employee does not belong to this department"
            })

        # ---------- Equipments ----------
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
                    "equipment_ids": "Some equipments do not belong to this department"
                })

            attrs["validated_equipments"] = equipments

        # ---------- Parameters ----------
        parameter_ids = attrs.get("parameter_ids", [])
        if parameter_ids:
            parameters = Parameters.objects.filter(
                id__in=parameter_ids,
                equipment__dep=department,
                is_active=True
            )

            if parameters.count() != len(set(parameter_ids)):
                raise serializers.ValidationError({
                    "parameter_ids": (
                        "Some parameters do not belong to selected equipment/department"
                    )
                })

            attrs["validated_parameters"] = parameters

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
        parameters = validated_data.pop("validated_parameters", [])
        schedule_data = validated_data.pop("schedule")

        # ---------- Event ----------
        event = Event.objects.create(
            department=department,
            assignment=assignment,
            event_name=validated_data["event_name"],
            description=validated_data["description"]
        )

        # ---------- Schedule ----------
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

        # ---------- Link Parameters ----------
        for parameter in parameters:
            EventParameter.objects.create(
                event=event,
                parameter=parameter
            )

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

        task = Task.objects.create(**validated_data)

        for sub in sub_tasks_data:
            SubTask.objects.create(
                task=task,
                assignment=task.assignment,
                **sub
            )

        for doc in documents_data:
            Document.objects.create(
                task=task,
                **doc
            )

        return task

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
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # =================================================
        # SUB TASKS (ID SAFE)
        # =================================================
        existing_subtasks = {
            st.id: st for st in instance.subtask_set.all()
        }
        received_subtask_ids = []

        for sub in sub_tasks_data:
            sub_id = sub.get("id")

            if sub_id:
                # UPDATE
                obj = existing_subtasks.get(sub_id)
                if not obj:
                    raise serializers.ValidationError({
                        "sub_tasks": f"SubTask {sub_id} does not belong to this task"
                    })

                obj.due_date = sub["due_date"]
                obj.description = sub["description"]
                obj.status = sub.get("status", obj.status)
                obj.save()

                received_subtask_ids.append(sub_id)
            else:
                # CREATE
                obj = SubTask.objects.create(
                    task=instance,
                    assignment=instance.assignment,
                    **sub
                )
                received_subtask_ids.append(obj.id)

        # DELETE removed subtasks
        for sub_id, obj in existing_subtasks.items():
            if sub_id not in received_subtask_ids:
                obj.delete()

        # =================================================
        # DOCUMENTS (ID SAFE)
        # =================================================
        existing_docs = {
            doc.id: doc for doc in instance.document_set.all()
        }
        received_doc_ids = []

        for doc in documents_data:
            doc_id = doc.get("id")

            if doc_id:
                # UPDATE
                obj = existing_docs.get(doc_id)
                if not obj:
                    raise serializers.ValidationError({
                        "documents": f"Document {doc_id} does not belong to this task"
                    })

                obj.document_name = doc.get(
                    "document_name", obj.document_name
                )
                if "data" in doc:
                    obj.data = doc["data"]
                obj.save()

                received_doc_ids.append(doc_id)
            else:
                # CREATE
                obj = Document.objects.create(
                    task=instance,
                    document_name=doc["document_name"],
                    data=doc["data"]
                )
                received_doc_ids.append(obj.id)

        # DELETE removed documents
        for doc_id, obj in existing_docs.items():
            if doc_id not in received_doc_ids:
                obj.delete()

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
