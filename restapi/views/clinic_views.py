# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import logging
import traceback

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from drf_yasg.utils import swagger_auto_schema

from django.shortcuts import get_object_or_404

from restapi.models import Clinic, Department, Employee
from restapi.serializers.clinic import ClinicSerializer, ClinicReadSerializer, DepartmentReadSerializer
from restapi.serializers.employee import EmployeeReadSerializer

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Create Clinic (POST) + List Clinics (GET)
# -------------------------------------------------------------------
class ClinicCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Get all ACTIVE clinics with departments",
        responses={200: ClinicReadSerializer(many=True)},
    )
    def get(self, request):
        try:
            clinics = Clinic.objects.filter(is_active=True).order_by("-id")

            serializer = ClinicReadSerializer(clinics, many=True)

            return Response(
                {
                    "success": True,
                    "message": "Clinics fetched successfully",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception:
            logger.error("Unhandled Clinic List Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        operation_description="Create a new clinic with departments",
        request_body=ClinicSerializer,
        responses={
            201: ClinicReadSerializer,
            400: "Validation Error",
            500: "Internal Server Error",
        },
    )
    def post(self, request):
        try:
            # 🔥 Ensure departments are passed
            if not request.data.get("department"):
                raise ValidationError({"department": "At least one department is required"})

            serializer = ClinicSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            clinic = serializer.save()

            return Response(
                ClinicReadSerializer(clinic).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as ve:
            logger.warning(f"Clinic validation failed: {ve.detail}")
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Unhandled Clinic Create Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -------------------------------------------------------------------
# Update Clinic (PUT)
# -------------------------------------------------------------------
class ClinicUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Update an ACTIVE clinic and its departments",
        request_body=ClinicSerializer,
        responses={
            200: ClinicReadSerializer,
            400: "Validation Error",
            404: "Clinic not found",
            500: "Internal Server Error",
        },
    )
    def put(self, request, clinic_id):
        try:
            clinic = Clinic.objects.get(id=clinic_id, is_active=True)

            serializer = ClinicSerializer(clinic, data=request.data)
            serializer.is_valid(raise_exception=True)

            updated_clinic = serializer.save()

            return Response(
                ClinicReadSerializer(updated_clinic).data,
                status=status.HTTP_200_OK,
            )

        except Clinic.DoesNotExist:
            logger.warning("Clinic not found or inactive")
            raise NotFound("Clinic not found")

        except ValidationError as ve:
            logger.warning(f"Clinic update validation failed: {ve.detail}")
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Unhandled Clinic Update Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -------------------------------------------------------------------
# Get Clinic by ID (GET)
# -------------------------------------------------------------------
class GetClinicView(APIView):

    @swagger_auto_schema(
        operation_description="Retrieve ACTIVE clinic details with departments",
        responses={
            200: ClinicReadSerializer,
            404: "Clinic not found",
            500: "Internal Server Error",
        },
    )
    def get(self, request, clinic_id=None):
        try:
            resolved_clinic_id = (
                request.query_params.get("clinic_id")
                or request.headers.get("X-Clinic-Id")
                or clinic_id
            )

            clinic = Clinic.objects.get(
                id=resolved_clinic_id,
                is_active=True,
            )

            serializer = ClinicReadSerializer(clinic)

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Clinic.DoesNotExist:
            raise NotFound("Clinic not found")

        except Exception:
            logger.error("Unhandled Clinic Fetch Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -------------------------------------------------------------------
# Search Clinics (GET)
# -------------------------------------------------------------------
class ClinicSearchAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Search ACTIVE clinics by name",
        responses={200: ClinicReadSerializer(many=True)},
    )
    def get(self, request):
        try:
            query = request.query_params.get("q", "").strip()

            clinics = Clinic.objects.filter(is_active=True)

            if query:
                clinics = clinics.filter(name__icontains=query)

            clinics = clinics.order_by("-id")

            serializer = ClinicReadSerializer(clinics, many=True)

            return Response(
                {
                    "success": True,
                    "message": "Clinics fetched successfully",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception:
            logger.error("Unhandled Clinic Search Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -------------------------------------------------------------------
# Clinic Employees API View (GET)
# -------------------------------------------------------------------
class ClinicEmployeesAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Get Clinic Employees",
        operation_description="Retrieve all employees under an ACTIVE clinic",
        responses={
            200: EmployeeReadSerializer(many=True),
            404: "Clinic not found",
        },
        tags=["Clinic"]
    )
    def get(self, request, clinic_id):

        get_object_or_404(Clinic, id=clinic_id, is_active=True)

        employees = Employee.objects.filter(clinic_id=clinic_id)
        serializer = EmployeeReadSerializer(employees, many=True)
        return Response(serializer.data)


# -------------------------------------------------------------------
# Departments by Clinic
# -------------------------------------------------------------------
class DepartmentListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Get active departments by clinic",
        responses={200: DepartmentReadSerializer(many=True)},
        tags=["Clinic"]
    )
    def get(self, request):

        clinic_id = request.query_params.get("clinic_id")

        if not clinic_id:
            return Response({"error": "clinic_id is required"}, status=400)

        try:
            clinic = Clinic.objects.get(id=clinic_id, is_active=True)
        except Clinic.DoesNotExist:
            return Response({"error": "Clinic not found"}, status=404)

        departments = Department.objects.filter(
            clinic=clinic,
            is_active=True
        ).order_by("name")

        serializer = DepartmentReadSerializer(departments, many=True)
        return Response(serializer.data)
