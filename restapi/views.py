from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import TaskSerializer
from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import NotFound, ValidationError
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import traceback
import logging
from django.utils import timezone
from .pagination import StandardResultsPagination
from rest_framework.pagination import PageNumberPagination
from .models import (Clinic, Department, Environment_Parameter_Value, Equipments,Event, Task, Employee, SubTask, ParameterValues,Department,
Environment, Environment_Parameter, Environment_Parameter_Value, Task_Event)
from .serializers import (
    ClinicSerializer,
    ClinicReadSerializer,
    EquipmentSerializer,
    DepartmentSerializer,
    EventCreateSerializer,
    EventReadSerializer,
    TaskSerializer, TaskReadSerializer,
    TaskEventReadSerializer, 
    TaskEventSerializer,
    EmployeeReadSerializer,
    UserCreateSerializer,
    EmployeeCreateSerializer,
    ParameterValueCreateSerializer,
    ParameterValueReadSerializer,
    EnvironmentSerializer,
    EnvironmentParameterPatchSerializer,
    EnvironmentParameterValueSerializer, 
    
)

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# 1. Create Clinic (POST)
# -------------------------------------------------------------------
class ClinicCreateAPIView(APIView):
    
    

    @swagger_auto_schema(
        operation_description="Create a new clinic",
        request_body=ClinicSerializer,   #  WRITE
        responses={
            201: ClinicReadSerializer,        # ✅ READ
            400: "Validation Error",
            500: "Internal Server Error"
        }
    )
    def post(self, request):
        try:
            serializer = ClinicSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            clinic = serializer.save()

            return Response(
                ClinicReadSerializer(clinic).data,
                status=status.HTTP_201_CREATED
            )

        except ValidationError as ve:
            logger.warning(f"Clinic validation failed: {ve.detail}")
            return Response({"error": ve.detail}, status=400)

        except Exception:
            logger.error(
                "Unhandled Clinic Create Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=500
            )


# -------------------------------------------------------------------
# 2. Update Clinic (PUT)
# -------------------------------------------------------------------
class ClinicUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Update an existing clinic",
        request_body=ClinicSerializer,
        responses={
            200: ClinicSerializer,
            400: "Validation Error",
            404: "Clinic not found",
            500: "Internal Server Error",
        }
    )
    def put(self, request, clinic_id):
        try:
            # ✅ fetch existing clinic
            clinic = Clinic.objects.get(id=clinic_id)

            # ✅ IMPORTANT: instance + data (PUT = full update)
            serializer = ClinicSerializer(
                clinic,
                data=request.data
            )

            serializer.is_valid(raise_exception=True)

            # ✅ calls serializer.update() (not create)
            updated = serializer.save()

            return Response(
                ClinicReadSerializer(updated).data,
                status=status.HTTP_200_OK
            )

        except Clinic.DoesNotExist:
            logger.warning("Clinic not found")
            raise NotFound("Clinic not found")

        except ValidationError as ve:
            logger.warning(
                f"Clinic update validation failed: {ve.detail}"
            )
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception:
            logger.error(
                "Unhandled Clinic Update Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# -------------------------------------------------------------------
# 3. Get Clinic by ID (GET)
# -------------------------------------------------------------------
class GetClinicView(APIView):
    


    @swagger_auto_schema(
        operation_description="Retrieve clinic details by ID",
        responses={
            200: ClinicReadSerializer,
            404: "Clinic not found",
            500: "Internal Server Error"
        }
    )
    def get(self, request, clinic_id):
        try:
            clinic = Clinic.objects.get(id=clinic_id)
            serializer = ClinicReadSerializer(clinic)

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Clinic.DoesNotExist:
            logger.warning("Clinic not found")
            raise NotFound("Clinic not found")

        except Exception:
            logger.error("Unhandled Clinic Fetch Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=500)


# -------------------------------------------------------------------
# 4. Create Equipment under Department (POST)
# -------------------------------------------------------------------
class DepartmentEquipmentCreateAPIView(APIView):
    
    

    @swagger_auto_schema(
        operation_description="Create equipment under a specific department",
        request_body=EquipmentSerializer,
        responses={
            201: EquipmentSerializer,
            400: "Validation Error",
            404: "Department not found",
            500: "Internal Server Error"
        }
    )
    def post(self, request, department_id):
        try:
            department = Department.objects.get(id=department_id)

            serializer = EquipmentSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            #  SAME AS BEFORE – serializer handles ParameterValues internally
            equipment = serializer.save(dep=department)

            return Response(
                EquipmentSerializer(equipment).data,
                status=status.HTTP_201_CREATED
            )

        except Department.DoesNotExist:
            logger.warning("Department not found")
            raise NotFound("Department not found")

        except ValidationError as ve:
            logger.warning(f"Equipment validation failed: {ve.detail}")
            return Response({"error": ve.detail}, status=400)

        except Exception:
            logger.error("Unhandled Equipment Create Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=500)


# -------------------------------------------------------------------
# 5. Update Equipment under Department (PUT)
# -------------------------------------------------------------------
class DepartmentEquipmentUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Update an existing equipment under a specific department",
        request_body=EquipmentSerializer,
        responses={
            200: EquipmentSerializer,
            400: "Validation Error",
            404: "Not found",
            500: "Internal Server Error",
        }
    )
    def put(self, request, department_id, equipment_id):
        try:
            # 1️⃣ Validate Department
            try:
                department = Department.objects.get(id=department_id)
            except Department.DoesNotExist:
                return Response(
                    {"error": "Department not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # 2️⃣ Validate Equipment exists
            try:
                equipment = Equipments.objects.get(id=equipment_id)
            except Equipments.DoesNotExist:
                return Response(
                    {"error": "Equipment not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # 3️⃣ Validate Equipment belongs to Department
            if equipment.dep_id != department.id:
                return Response(
                    {
                        "error": "Equipment does not belong to this department"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 4️⃣ Update Equipment
            serializer = EquipmentSerializer(
                equipment,
                data=request.data
            )
            serializer.is_valid(raise_exception=True)
            updated = serializer.save()

            return Response(
                EquipmentSerializer(updated).data,
                status=status.HTTP_200_OK
            )

        except ValidationError as ve:
            logger.warning(
                f"Equipment update validation failed: {ve.detail}"
            )
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception:
            logger.error(
                "Unhandled Equipment Update Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



# -------------------------------------------------------------------
# 6. Inactivate Equipment (PATCH)
# -------------------------------------------------------------------
class EquipmentInactiveAPIView(APIView):
    
    

    @swagger_auto_schema(
        operation_description="Mark equipment as inactive",
        responses={
            200: "Equipment marked inactive",
            404: "Equipment not found",
            500: "Internal Server Error"
        }
    )
    def patch(self, request, department_id, equipment_id):
        try:
            equipment = Equipments.objects.get(
                id=equipment_id,
                dep_id=department_id
            )
            equipment.is_active = False
            equipment.save()

            return Response(
                {"message": "Equipment marked as inactive"},
                status=status.HTTP_200_OK
            )

        except Equipments.DoesNotExist:
            logger.warning("Equipment not found")
            raise NotFound("Equipment not found")

        except Exception:
            logger.error("Unhandled Equipment Inactivate Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=500)

# -------------------------------------------------------------------
# 7. Soft Delete Equipment (PATCH/DELETE)
# -------------------------------------------------------------------
class EquipmentSoftDeleteAPIView(APIView):
    
   

    @swagger_auto_schema(
        operation_description="Soft delete equipment",
        responses={
            200: "Equipment soft deleted",
            404: "Equipment not found",
            500: "Internal Server Error"
        }
    )
    def patch(self, request, department_id, equipment_id):
        try:
            equipment = Equipments.objects.get(
                id=equipment_id,
                dep_id=department_id,
                is_deleted=False
            )

            equipment.is_deleted = True
            equipment.is_active = False
            equipment.save()

            return Response(
                {"message": "Equipment soft deleted"},
                status=status.HTTP_200_OK
            )

        except Equipments.DoesNotExist:
            logger.warning("Equipment not found")
            raise NotFound("Equipment not found")

        except Exception:
            logger.error(
                "Unhandled Equipment Soft Delete Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=500
            )

    # ADD THIS METHOD (THIS IS WHAT FIXES DELETE)
    def delete(self, request, department_id, equipment_id):
        return self.patch(request, department_id, equipment_id)

# -------------------------------------------------------------------
# 7. Event API View (POST)
# -------------------------------------------------------------------
class EventAPIView(APIView):
    
   
    @swagger_auto_schema(
        operation_summary="Create Event",
        operation_description=(
            "Create a new event.\n\n"
            "The event owner (assignment) is automatically taken from the "
            "logged-in user's Employee profile."
        ),
        request_body=EventCreateSerializer,
        responses={
            201: EventReadSerializer,
            400: openapi.Response(
                description="Validation Error"
            ),
            401: openapi.Response(
                description="Unauthorized"
            ),
            500: openapi.Response(
                description="Internal Server Error"
            ),
        },
        tags=["Event"]
    )
    def post(self, request):
        serializer = EventCreateSerializer(
            data=request.data,
            context={"request": request}  # 🔑 IMPORTANT
        )

        try:
            serializer.is_valid(raise_exception=True)
            event = serializer.save()

            return Response(
                EventReadSerializer(event).data,
                status=status.HTTP_201_CREATED
            )

        except ValidationError as ve:
            return Response(
                ve.detail,
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception:
            logger.error("Event Create Error", exc_info=True)
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        


# -------------------------------------------------------------------
# Clinic Event List API View (GET – No Pagination)
# -------------------------------------------------------------------
class ClinicEventListAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Get All Events by Clinic",
        operation_description=(
            "Retrieve all events associated with a given clinic.\n\n"
            "Behavior:\n"
            "- Validates the clinic ID\n"
            "- Fetches all events linked to the clinic via departments\n"
            "- Returns events ordered by latest created first\n\n"
            "Note:\n"
            "- This API does NOT use pagination\n"
            "- All events are returned in a single response"
        ),
        manual_parameters=[
            openapi.Parameter(
                name="clinic_id",
                in_=openapi.IN_PATH,
                type=openapi.TYPE_INTEGER,
                required=True,
                description="Clinic ID to fetch all events"
            )
        ],
        responses={
            200: openapi.Response(
                description="Events fetched successfully",
                schema=EventReadSerializer(many=True)
            ),
            404: "Clinic not found",
            500: "Internal Server Error"
        },
        tags=["Event"]
    )
    def get(self, request, clinic_id):
        # ✅ Validate clinic
        get_object_or_404(Clinic, id=clinic_id)

        # ✅ Fetch all events for the clinic (no pagination)
        queryset = Event.objects.filter(
            department__clinic_id=clinic_id
        ).order_by("-created_at")

        serializer = EventReadSerializer(queryset, many=True)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    
# -------------------------------------------------------------------
# 9. Task Create and Update API Views
# -------------------------------------------------------------------


class TaskCreateAPIView(APIView):
   

    @swagger_auto_schema(
        operation_summary="Create Task",
        operation_description=(
            "Create a new task with optional subtasks and document.\n\n"
            "If subtask status is not provided, it defaults to TODO (0)."
        ),
        request_body=TaskSerializer,
        responses={
            201: TaskReadSerializer,
            400: openapi.Response(description="Validation Error"),
            401: openapi.Response(description="Unauthorized"),
            500: openapi.Response(description="Internal Server Error"),
        },
        tags=["Task"]
    )
    def post(self, request):
        serializer = TaskSerializer(
            data=request.data,
            context={"request": request}
        )

        try:
            serializer.is_valid(raise_exception=True)
            task = serializer.save()

            return Response(
                TaskReadSerializer(task).data,
                status=status.HTTP_201_CREATED
            )

        except ValidationError as ve:
            return Response(
                ve.detail,
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception:
            logger.error("Task Create Error", exc_info=True)
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# -------------------------------------------------------------------
# 10. Task Update API View
# -------------------------------------------------------------------


class TaskUpdateAPIView(APIView):
    
    @swagger_auto_schema(
        operation_summary="Update Task",
        operation_description=(
            "Update an existing task.\n\n"
            "This is a full replace operation. "
            "Existing subtasks will be deleted and recreated if provided."
        ),
        request_body=TaskSerializer,
        responses={
            200: TaskReadSerializer,
            400: openapi.Response(description="Validation Error"),
            401: openapi.Response(description="Unauthorized"),
            404: openapi.Response(description="Task Not Found"),
            500: openapi.Response(description="Internal Server Error"),
        },
        tags=["Task"]
    )
    def put(self, request, task_id):
        task = get_object_or_404(Task, id=task_id)

        serializer = TaskSerializer(
            task,
            data=request.data,
            context={"request": request}
        )

        try:
            serializer.is_valid(raise_exception=True)
            task = serializer.save()

            return Response(
                TaskReadSerializer(task).data,
                status=status.HTTP_200_OK
            )

        except ValidationError as ve:
            return Response(
                ve.detail,
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception:
            logger.error("Task Update Error", exc_info=True)
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
# -------------------------------------------------------------------
# 12. Task Get API View
# -------------------------------------------------------------------
class TaskGetAPIView(APIView):
    

    @swagger_auto_schema(
        operation_summary="Get Task",
        operation_description="Retrieve task details by task ID",
        responses={
            200: TaskReadSerializer,
            401: openapi.Response(description="Unauthorized"),
            404: openapi.Response(description="Task Not Found"),
        },
        tags=["Task"]
    )
    def get(self, request, task_id):
        task = get_object_or_404(
            Task,
            id=task_id,
            is_deleted=False
        )

        return Response(
            TaskReadSerializer(task).data,
            status=status.HTTP_200_OK
        )

# -------------------------------------------------------------------
# Task Get By Event ID API View
# -------------------------------------------------------------------
class TaskGetByEventAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Get Tasks By Event ID",
        operation_description="Retrieve all tasks associated with a given event ID",
        responses={
            200: TaskReadSerializer(many=True),
            401: openapi.Response(description="Unauthorized"),
            404: openapi.Response(description="No Tasks Found"),
        },
        tags=["Task"]
    )
    def get(self, request, event_id):
        tasks = Task.objects.filter(
            event_id=event_id,
            is_deleted=False
        ).order_by("-created_at")

        if not tasks.exists():
            raise NotFound("No tasks found for this event")

        return Response(
            TaskReadSerializer(tasks, many=True).data,
            status=status.HTTP_200_OK
        )



# -------------------------------------------------------------------
# 13. Clinic Employees API View (GET)
# -------------------------------------------------------------------

class ClinicEmployeesAPIView(APIView):
    
    @swagger_auto_schema(
        operation_summary="Get Clinic Employees",
        operation_description="Retrieve all employees under a specific clinic",
        responses={
            200: EmployeeReadSerializer(many=True),
            401: "Unauthorized",
            404: "Clinic not found",
        },
        tags=["Clinic"]
    )
    def get(self, request, clinic_id):
        #  Validate clinic existence
        get_object_or_404(Clinic, id=clinic_id)

        #  Fetch employees for the clinic
        employees = Employee.objects.filter(clinic_id=clinic_id)

        serializer = EmployeeReadSerializer(employees, many=True)
        return Response(serializer.data)

# -------------------------------------------------------------------
# 14. Employee Create API View (POST)
# -------------------------------------------------------------------

class EmployeeCreateAPIView(APIView):
   

    @swagger_auto_schema(
        operation_summary="Create Employee",
        operation_description="Create an employee under a clinic and department",
        request_body=EmployeeCreateSerializer,
        responses={
            201: EmployeeReadSerializer,
            400: "Validation Error",
            401: "Unauthorized"
        },
        tags=["Employee"]
    )
    def post(self, request):
        serializer = EmployeeCreateSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        employee = serializer.save()

        return Response(
            EmployeeReadSerializer(employee).data,
            status=status.HTTP_201_CREATED
        )
    
# -------------------------------------------------------------------
# 15. Task Soft Delete API
# -------------------------------------------------------------------
class TaskSoftDeleteAPIView(APIView):
    
    @swagger_auto_schema(
        operation_summary="Soft Delete Task",
        operation_description=(
            "Soft delete a task and all its subtasks"
        ),
        responses={
            200: "Task and subtasks soft deleted",
            401: "Unauthorized",
            404: "Task Not Found",
        },
        tags=["Task"]
    )
    def patch(self, request, task_id):
        task = get_object_or_404(
            Task,
            id=task_id,
            is_deleted=False
        )

        #  Soft delete task
        task.is_deleted = True
        task.save()

        #  Soft delete all subtasks
        task.subtask_set.update(is_deleted=True)

        return Response(
            {"message": "Task and subtasks soft deleted"},
            status=status.HTTP_200_OK
        )

    # Optional DELETE support
    def delete(self, request, task_id):
        return self.patch(request, task_id)

# -------------------------------------------------------------------
# 16. SubTask Soft Delete API
# -------------------------------------------------------------------
class SubTaskSoftDeleteAPIView(APIView):
    
    @swagger_auto_schema(
        operation_summary="Soft Delete SubTask",
        responses={
            200: "SubTask soft deleted",
            401: "Unauthorized",
            404: "SubTask Not Found",
        },
        tags=["SubTask"]
    )
    def patch(self, request, subtask_id):
        subtask = get_object_or_404(
            SubTask,
            id=subtask_id,
            is_deleted=False
        )

        subtask.is_deleted = True
        subtask.save()

        return Response(
            {"message": "SubTask soft deleted"},
            status=status.HTTP_200_OK
        )

# -------------------------------------------------------------------
# 17. User Create API View (POST)
# -------------------------------------------------------------------


class UserCreateAPIView(APIView):
    
    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                "id": user.id,
                "username": user.username
            },
            status=status.HTTP_201_CREATED
        )
    
# -------------------------------------------------------------------
# 18. Parameter Value Create and List API Views
# -------------------------------------------------------------------

class ParameterValueCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Create Parameter Value",
        operation_description=(
            "Create a runtime reading for a parameter.\n\n"
            "This API stores live readings (e.g., Oxygen level, BP, ECG) "
            "and does NOT modify parameter config."
        ),
        request_body=ParameterValueCreateSerializer,
        responses={
            201: openapi.Response(
                description="Parameter value created successfully",
                schema=ParameterValueCreateSerializer
            ),
            400: "Validation Error",
            500: "Internal Server Error"
        },
        tags=["Parameter Values"]
    )
    def post(self, request):
        serializer = ParameterValueCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        value = serializer.save()

        return Response(
            ParameterValueCreateSerializer(value).data,
            status=status.HTTP_201_CREATED
        )

# -------------------------------------------------------------------
# 19. Parameter Value List API View (GET)
# -------------------------------------------------------------------

class ParameterValueListAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="List Parameter Values",
        operation_description=(
            "Retrieve all runtime readings for a given parameter.\n\n"
            "Results are ordered by latest first."
        ),
        manual_parameters=[
            openapi.Parameter(
                name="parameter_id",
                in_=openapi.IN_PATH,
                type=openapi.TYPE_INTEGER,
                required=True,
                description="Parameter ID"
            )
        ],
        responses={
            200: openapi.Response(
                description="List of parameter values",
                schema=ParameterValueReadSerializer(many=True)
            ),
            404: "Parameter not found",
            500: "Internal Server Error"
        },
        tags=["Parameter Values"]
    )
    def get(self, request, parameter_id):
        parameter = get_object_or_404(
            Parameters,
            id=parameter_id,
            is_active=True
        )

        values = ParameterValues.objects.filter(
            parameter=parameter,
            is_deleted=False
        ).order_by("-created_at")

        serializer = ParameterValueReadSerializer(values, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# -------------------------------------------------------------------
# 20. Activate Equipment API View (POST)
# -------------------------------------------------------------------

class ActivateEquipmentAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Activate Equipment",
        operation_description=(
            "Activate a previously inactivated equipment.\n\n"
            "This API sets is_active = true for the given equipment ID.\n"
            "No other equipment data (details, parameters, config history) is modified."
        ),
        manual_parameters=[
            openapi.Parameter(
                name="equipment_id",
                in_=openapi.IN_PATH,
                type=openapi.TYPE_INTEGER,
                required=True,
                description="Equipment ID to activate"
            )
        ],
        responses={
            200: openapi.Response(
                description="Equipment activated successfully"
            ),
            404: "Equipment not found",
            500: "Internal Server Error"
        },
        tags=["Equipment"]
    )
    def post(self, request, equipment_id):
        equipment = get_object_or_404(
            Equipments,
            id=equipment_id,
            is_deleted=False
        )

        # Activate equipment
        equipment.is_active = True
        equipment.save(update_fields=["is_active"])

        return Response(
            {"message": "Equipment activated successfully"},
            status=status.HTTP_200_OK
        )


# -------------------------------------------------------------------
# 21. Soft Delete Parameter API View (PATCH)
# -------------------------------------------------------------------
class SoftDeleteParameterAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Soft Delete Parameter",
        operation_description=(
            "Soft delete a parameter using parameter ID.\n\n"
            "This API performs a soft delete by setting:\n"
            "- is_deleted = true\n"
            "- is_active = false\n"
            "- deleted_at = current timestamp\n\n"
            "No equipment or other parameters are affected."
        ),
        manual_parameters=[
            openapi.Parameter(
                name="parameter_id",
                in_=openapi.IN_PATH,
                type=openapi.TYPE_INTEGER,
                required=True,
                description="Parameter ID to soft delete"
            )
        ],
        responses={
            200: openapi.Response(
                description="Parameter soft deleted successfully"
            ),
            404: "Parameter not found or already deleted",
            500: "Internal Server Error"
        },
        tags=["Parameter"]
    )
    def patch(self, request, parameter_id):
        parameter = get_object_or_404(
            Parameters,
            id=parameter_id,
            is_deleted=False
        )

        # 🔒 Soft delete parameter
        parameter.is_deleted = True
        parameter.is_active = False
        parameter.deleted_at = timezone.now()

        parameter.save(
            update_fields=["is_deleted", "is_active", "deleted_at"]
        )

        return Response(
            {"message": "Parameter soft deleted successfully"},
            status=status.HTTP_200_OK
        )
    
# -------------------------------------------------------------------
# 22. Task Timer Start API View (POST)
# -------------------------------------------------------------------
class TaskTimerStartAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Start Task Timer",
        operation_description=(
            "Start timer for a task.\n\n"
            "Behavior:\n"
            "- If timer is already RUNNING → no operation\n"
            "- If timer was PAUSED:\n"
            "  - resumes timer without losing previously tracked time\n"
            "- Else:\n"
            "  - timer_status = RUNNING\n"
            "  - timer_started_at = current timestamp\n\n"
            "Previously tracked time is preserved and new tracking "
            "starts from the current timestamp."
        ),
        manual_parameters=[
            openapi.Parameter(
                name="id",
                in_=openapi.IN_PATH,
                type=openapi.TYPE_INTEGER,
                required=True,
                description="Task ID"
            )
        ],
        responses={
            200: openapi.Response(
                description="Timer started successfully or already running"
            ),
            404: "Task not found",
            500: "Internal Server Error"
        },
        tags=["Task Timer"]
    )
    def post(self, request, id):
        task = get_object_or_404(Task, id=id, is_deleted=False)

        # ⏱ No-op if already running
        if task.timer_status == Task.TIMER_RUNNING:
            return Response(
                {"message": "Timer already running"},
                status=status.HTTP_200_OK
            )

        # ▶ Resume or fresh start — timestamp is always reset
        task.timer_status = Task.TIMER_RUNNING
        task.timer_started_at = timezone.now()

        task.save(
            update_fields=[
                "timer_status",
                "timer_started_at"
            ]
        )

        return Response(
            {"message": "Timer started successfully"},
            status=status.HTTP_200_OK
        )


# -------------------------------------------------------------------
# 23. Task Timer Pause API View (POST)
# -------------------------------------------------------------------
class TaskTimerPauseAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Pause Task Timer",
        operation_description=(
            "Pause timer for a task.\n\n"
            "Behavior:\n"
            "- If timer is RUNNING:\n"
            "  - elapsed time (now - timer_started_at) is added to total_tracked_sec\n"
            "- timer_status is set to PAUSED\n"
            "- timer_started_at is cleared\n\n"
            "Safe to call even if timer is not running."
        ),
        manual_parameters=[
            openapi.Parameter(
                name="id",
                in_=openapi.IN_PATH,
                type=openapi.TYPE_INTEGER,
                required=True,
                description="Task ID"
            )
        ],
        responses={
            200: openapi.Response(
                description="Timer paused successfully"
            ),
            404: "Task not found",
            500: "Internal Server Error"
        },
        tags=["Task Timer"]
    )
    def post(self, request, id):
        task = get_object_or_404(Task, id=id, is_deleted=False)

        if task.timer_status == Task.TIMER_RUNNING and task.timer_started_at:
            elapsed = int(
                (timezone.now() - task.timer_started_at).total_seconds()
            )
            task.total_tracked_sec += elapsed

        task.timer_status = Task.TIMER_PAUSED
        task.timer_started_at = None

        task.save(
            update_fields=[
                "timer_status",
                "timer_started_at",
                "total_tracked_sec"
            ]
        )

        return Response(
            {"message": "Timer paused successfully"},
            status=status.HTTP_200_OK
        )

# -------------------------------------------------------------------
# 24. Task Timer Stop API View (POST)
# -------------------------------------------------------------------   
class TaskTimerStopAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Stop Task Timer",
        operation_description=(
            "Stop timer for a task and mark task as completed.\n\n"
            "Behavior:\n"
            "- If timer is RUNNING:\n"
            "  - elapsed time (now - timer_started_at) is added to total_tracked_sec\n"
            "- timer_status is set to STOPPED\n"
            "- timer_started_at is cleared\n"
            "- task status is set to COMPLETED (2)\n\n"
            "This is a terminal operation for task timing."
        ),
        manual_parameters=[
            openapi.Parameter(
                name="id",
                in_=openapi.IN_PATH,
                type=openapi.TYPE_INTEGER,
                required=True,
                description="Task ID"
            )
        ],
        responses={
            200: openapi.Response(
                description="Timer stopped and task completed successfully"
            ),
            404: "Task not found",
            500: "Internal Server Error"
        },
        tags=["Task Timer"]
    )
    def post(self, request, id):
        task = get_object_or_404(Task, id=id, is_deleted=False)

        if task.timer_status == Task.TIMER_RUNNING and task.timer_started_at:
            elapsed = int(
                (timezone.now() - task.timer_started_at).total_seconds()
            )
            task.total_tracked_sec += elapsed

        task.timer_status = Task.TIMER_STOPPED
        task.timer_started_at = None
        task.status = Task.COMPLETED

        task.save(
            update_fields=[
                "timer_status",
                "timer_started_at",
                "total_tracked_sec",
                "status"
            ]
        )

        return Response(
            {"message": "Timer stopped and task marked as completed"},
            status=status.HTTP_200_OK
        )

# -------------------------------------------------------------------
# Task Get By Clinic ID API View
# -------------------------------------------------------------------
class TaskGetByClinicAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Get Tasks By Clinic ID",
        operation_description=(
            "Retrieve all tasks under a clinic.\n\n"
            "Tasks are resolved via:\n"
            "Task → Event → Department → Clinic"
        ),
        responses={
            200: TaskReadSerializer(many=True),
            404: openapi.Response(description="No Tasks Found"),
        },
        tags=["Task"]
    )
    def get(self, request, clinic_id):
        # Validate clinic exists
        get_object_or_404(Clinic, id=clinic_id)

        tasks = (
            Task.objects
            .filter(
                event__department__clinic_id=clinic_id,
                is_deleted=False
            )
            .select_related(
                "event",
                "event__department"
            )
            .order_by("-created_at")
        )

        if not tasks.exists():
            raise NotFound("No tasks found for this clinic")

        return Response(
            TaskReadSerializer(tasks, many=True).data,
            status=status.HTTP_200_OK
        )
    

# -------------------------------------------------------------------
# 1. POST → Create Environment + Parameters
# -------------------------------------------------------------------
class EnvironmentCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create environment with parameters (nested)",
        request_body=EnvironmentSerializer,
        responses={201: EnvironmentSerializer},
        tags=["Environment"]
    )
    def post(self, request, department_id):
        try:
            department = Department.objects.get(id=department_id)

            serializer = EnvironmentSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            environment = serializer.save(dep=department)

            return Response(
                EnvironmentSerializer(environment).data,
                status=status.HTTP_201_CREATED
            )

        except Department.DoesNotExist:
            raise NotFound("Department not found")

        except Exception:
            logger.error(traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=500
            )


# -------------------------------------------------------------------
# 2. GET → Environment + Parameters
# -------------------------------------------------------------------
class EnvironmentGetAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Get environment with parameters",
        responses={200: EnvironmentSerializer},
        tags=["Environment"]
    )
    def get(self, request, environment_id):
        environment = get_object_or_404(
            Environment,
            id=environment_id,
            is_deleted=False
        )

        return Response(
            EnvironmentSerializer(environment).data,
            status=status.HTTP_200_OK
        )
    

# -------------------------------------------------------------------
# UPDATE Environment (PUT / PATCH)
# -------------------------------------------------------------------
class EnvironmentUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Update environment",
        request_body=EnvironmentSerializer,
        responses={200: EnvironmentSerializer},
        tags=["Environment"]
    )
    def put(self, request, environment_id):
        environment = get_object_or_404(
            Environment,
            id=environment_id,
            is_deleted=False
        )

        serializer = EnvironmentSerializer(
            environment,
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        environment = serializer.save()

        return Response(
            EnvironmentSerializer(environment).data,
            status=status.HTTP_200_OK
        )

    def patch(self, request, environment_id):
        environment = get_object_or_404(
            Environment,
            id=environment_id,
            is_deleted=False
        )

        serializer = EnvironmentSerializer(
            environment,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        environment = serializer.save()

        return Response(
            EnvironmentSerializer(environment).data,
            status=status.HTTP_200_OK
        )



# -------------------------------------------------------------------
# 3. PATCH → Update Environment Parameter
# -------------------------------------------------------------------
class EnvironmentParameterPatchAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Update environment parameter",
        request_body=EnvironmentParameterPatchSerializer,
        responses={200: EnvironmentParameterPatchSerializer},
        tags=["Environment Parameter"]
    )
    def patch(self, request, parameter_id):
        parameter = get_object_or_404(
            Environment_Parameter,
            id=parameter_id,
            is_deleted=False
        )

        serializer = EnvironmentParameterPatchSerializer(
            parameter,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )


# -------------------------------------------------------------------
# 4. POST → Create Environment Parameter Value
# -------------------------------------------------------------------
class EnvironmentParameterValueCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create environment parameter value (runtime)",
        request_body=EnvironmentParameterValueSerializer,
        responses={201: EnvironmentParameterValueSerializer},
        tags=["Environment Parameter Value"]
    )
    def post(self, request):
        serializer = EnvironmentParameterValueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        value = serializer.save()

        return Response(
            EnvironmentParameterValueSerializer(value).data,
            status=status.HTTP_201_CREATED
        )


# -------------------------------------------------------------------
# 5. GET → List Environment Parameter Values
# -------------------------------------------------------------------
class EnvironmentParameterValueListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Get environment parameter value by value ID",
        responses={200: EnvironmentParameterValueSerializer},
        tags=["Environment Parameter Value"]
    )
    def get(self, request, value_id):
        try:
            value = Environment_Parameter_Value.objects.get(
                id=value_id,
                is_deleted=False
            )

            return Response(
                EnvironmentParameterValueSerializer(value).data,
                status=status.HTTP_200_OK
            )

        except Environment_Parameter_Value.DoesNotExist:
            raise NotFound({
                "error": {
                    "code": "ENV_PARAMETER_VALUE_NOT_FOUND",
                    "message": f"Environment parameter value with id {value_id} does not exist"
                }
            })  
        
# ==================================================
# ENVIRONMENT – ACTIVATE (POST)
# ==================================================
class EnvironmentActivateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Activate an environment",
        tags=["Environment"]
    )
    def post(self, request, environment_id):
        try:
            environment = Environment.objects.get(
                id=environment_id,
                is_deleted=False
            )

            environment.is_active = True
            environment.save(update_fields=["is_active"])

            return Response(
                {"message": "Environment activated successfully"},
                status=status.HTTP_200_OK
            )

        except Environment.DoesNotExist:
            raise NotFound({
                "code": "ENVIRONMENT_NOT_FOUND",
                "message": f"Environment with id {environment_id} does not exist"
            })


# ==================================================
# ENVIRONMENT – INACTIVATE (PATCH)
# ==================================================
class EnvironmentInactivateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Inactivate an environment",
        tags=["Environment"]
    )
    def patch(self, request, environment_id):
        try:
            environment = Environment.objects.get(
                id=environment_id,
                is_deleted=False
            )

            environment.is_active = False
            environment.save(update_fields=["is_active"])

            return Response(
                {"message": "Environment inactivated successfully"},
                status=status.HTTP_200_OK
            )

        except Environment.DoesNotExist:
            raise NotFound({
                "code": "ENVIRONMENT_NOT_FOUND",
                "message": f"Environment with id {environment_id} does not exist"
            })



# -------------------------------------------------------------------
# PATCH → Soft Delete Environment
# -------------------------------------------------------------------
class EnvironmentSoftDeleteAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Soft delete an environment",
        tags=["Environment"]
    )
    def patch(self, request, environment_id):
        try:
            environment = Environment.objects.get(
                id=environment_id,
                is_deleted=False
            )

            environment.is_deleted = True
            environment.is_active = False

            environment.save(update_fields=["is_deleted", "is_active"])

            return Response(
                {"message": "Environment soft deleted successfully"},
                status=status.HTTP_200_OK
            )

        except Environment.DoesNotExist:
            raise NotFound({
                "code": "ENVIRONMENT_NOT_FOUND",
                "message": f"Environment with id {environment_id} does not exist"
            })

# ==================================================
# ENVIRONMENT PARAMETER – SOFT DELETE (PATCH)
# ==================================================
class EnvironmentParameterSoftDeleteAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Soft delete an environment parameter",
        tags=["Environment Parameter"]
    )
    def patch(self, request, parameter_id):
        try:
            parameter = Environment_Parameter.objects.get(
                id=parameter_id,
                is_deleted=False
            )

            # ✅ SOFT DELETE (NO deleted_at)
            parameter.is_deleted = True
            parameter.is_active = False

            parameter.save(update_fields=["is_deleted", "is_active"])

            return Response(
                {
                    "message": "Environment parameter soft deleted successfully",
                    "parameter_id": parameter_id
                },
                status=status.HTTP_200_OK
            )

        except Environment_Parameter.DoesNotExist:
            raise NotFound({
                "code": "ENV_PARAMETER_NOT_FOUND",
                "message": f"Environment parameter with id {parameter_id} does not exist"
            })
        
class TaskEventCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create a Task Event",
        request_body=TaskEventSerializer,
        responses={
            201: TaskEventReadSerializer,
            400: "Validation Error"
        }
    )
    def post(self, request):
        serializer = TaskEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task_event = serializer.save()

        return Response(
            TaskEventReadSerializer(task_event).data,
            status=status.HTTP_201_CREATED
        )


class TaskEventListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Get all Task Events OR Get Task Event by ID",
        manual_parameters=[
            openapi.Parameter(
                "dep_id",
                openapi.IN_QUERY,
                description="Filter by Department ID",
                type=openapi.TYPE_INTEGER
            )
        ],
        responses={200: TaskEventReadSerializer(many=True)}
    )
    def get(self, request, task_event_id=None):

        # 🔹 Case 1: Get by ID
        if task_event_id:
            task_event = get_object_or_404(
                Task_Event,
                id=task_event_id,
                is_deleted=False
            )
            serializer = TaskEventReadSerializer(task_event)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # 🔹 Case 2: List all
        queryset = Task_Event.objects.filter(is_deleted=False)

        dep_id = request.query_params.get("dep_id")
        if dep_id:
            queryset = queryset.filter(dep_id=dep_id)

        serializer = TaskEventReadSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
