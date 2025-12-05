from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Clinic, Department
from .serializers import ClinicSerializer, ClinicReadSerializer, EquipmentSerializer
import logging

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
#  1. Create Clinic (POST)
# -------------------------------------------------------------------
class ClinicCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create a new clinic",
        request_body=ClinicSerializer,
        responses={
            201: ClinicSerializer,
            400: "Validation Error",
            500: "Internal Server Error"
        }
    )
    def post(self, request):
        serializer = ClinicSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        clinic = serializer.save()
        return Response(ClinicSerializer(clinic).data, status=status.HTTP_201_CREATED)


# -------------------------------------------------------------------
#  2. Update Clinic (PUT)
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
            clinic = Clinic.objects.get(id=clinic_id)
        except Clinic.DoesNotExist:
            raise NotFound("Clinic not found")

        serializer = ClinicSerializer(clinic, data=request.data)
        serializer.is_valid(raise_exception=True)

        updated = serializer.save()
        return Response(ClinicSerializer(updated).data, status=status.HTTP_200_OK)


# -------------------------------------------------------------------
#  3. Get Clinic by ID (GET)
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
        except Clinic.DoesNotExist:
            raise NotFound("Clinic not found")

        serializer = ClinicReadSerializer(clinic)
        return Response(serializer.data, status=status.HTTP_200_OK)


# -------------------------------------------------------------------
#  4. Create Equipment under Department (POST)
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

        # Validate Department ID
        try:
            department = Department.objects.get(id=department_id)
        except Department.DoesNotExist:
            raise NotFound("Department not found")

        serializer = EquipmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        equipment = serializer.save(dep=department)
        return Response(EquipmentSerializer(equipment).data, status=status.HTTP_201_CREATED)
