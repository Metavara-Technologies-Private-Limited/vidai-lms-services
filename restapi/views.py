from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import TaskSerializer
from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import NotFound, ValidationError
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import traceback
from rest_framework.permissions import AllowAny
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticated
import logging
from django.utils import timezone
from .pagination import StandardResultsPagination
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from .models import Clinic, Department, Equipments,Event, Task, Employee, SubTask
from .serializers import (
    ClinicSerializer,
    ClinicReadSerializer,
    EquipmentSerializer,
    DepartmentSerializer,
    EventCreateSerializer,
    EventReadSerializer,
    TaskSerializer, TaskReadSerializer,
    EmployeeReadSerializer,
    UserCreateSerializer,
    EmployeeCreateSerializer,
    
)

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# 1. Create Clinic (POST)
# -------------------------------------------------------------------
class ClinicCreateAPIView(APIView):
    
    permission_classes = [IsAuthenticated]

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
    
    permission_classes = [IsAuthenticated]

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
            clinic = Clinic.objects.get(id=clinic_id)

            serializer = ClinicSerializer(clinic, data=request.data)
            serializer.is_valid(raise_exception=True)

            updated = serializer.save()

            return Response(
                ClinicReadSerializer(updated).data,
                status=status.HTTP_200_OK
            )

        except Clinic.DoesNotExist:
            logger.warning("Clinic not found")
            raise NotFound("Clinic not found")

        except ValidationError as ve:
            logger.warning(f"Clinic update validation failed: {ve.detail}")
            return Response({"error": ve.detail}, status=400)

        except Exception:
            print(traceback.format_exc)
            logger.error("Unhandled Clinic Update Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=500)


# -------------------------------------------------------------------
# 3. Get Clinic by ID (GET)
# -------------------------------------------------------------------
class GetClinicView(APIView):
    authentication_classes = [
        JWTAuthentication,          # ✅ REQUIRED
        SessionAuthentication,
        BasicAuthentication
    ]
    permission_classes = [IsAuthenticated]  # optional, but recommended


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
    
    permission_classes = [IsAuthenticated]

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
    
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Update an existing equipment under a specific department",
        request_body=EquipmentSerializer,
        responses={
            200: EquipmentSerializer,
            400: "Validation Error",
            404: "Equipment not found",
            500: "Internal Server Error",
        }
    )
    def put(self, request, department_id, equipment_id):
        try:
            equipment = Equipments.objects.get(
                id=equipment_id,
                dep_id=department_id
            )

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

        except Equipments.DoesNotExist:
            logger.warning("Equipment not found")
            raise NotFound("Equipment not found")

        except ValidationError as ve:
            logger.warning(f"Equipment update validation failed: {ve.detail}")
            return Response({"error": ve.detail}, status=400)

        except Exception:
            logger.error("Unhandled Equipment Update Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=500
            )



# -------------------------------------------------------------------
# 6. Inactivate Equipment (PATCH)
# -------------------------------------------------------------------
class EquipmentInactiveAPIView(APIView):
    
    permission_classes = [IsAuthenticated]

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
    
    permission_classes = [IsAuthenticated]

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
    
    permission_classes = [IsAuthenticated]

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
# 8. Event API View (GET)
# -------------------------------------------------------------------

class ClinicEventListAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, clinic_id):
        #  Validate clinic
        get_object_or_404(Clinic, id=clinic_id)

        queryset = Event.objects.filter(
            department__clinic_id=clinic_id
        ).order_by("-created_at")

        paginator = PageNumberPagination()
        paginator.page_size = 10

        page = paginator.paginate_queryset(
            queryset=queryset,
            request=request,
            view=self
        )

        # 🔑 THIS CHECK IS MANDATORY
        if page is not None:
            serializer = EventReadSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        # fallback (never errors)
        serializer = EventReadSerializer(queryset, many=True)
        return Response(serializer.data)
    
# -------------------------------------------------------------------
# 9. Task Create and Update API Views
# -------------------------------------------------------------------


class TaskCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
# 13. Clinic Employees API View (GET)
# -------------------------------------------------------------------

class ClinicEmployeesAPIView(APIView):
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
    permission_classes = [AllowAny]   

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
    



