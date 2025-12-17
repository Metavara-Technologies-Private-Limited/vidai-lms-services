from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from drf_yasg.utils import swagger_auto_schema
import traceback
import logging

from .models import Clinic, Department, Equipments
from .serializers import (
    ClinicSerializer,
    ClinicReadSerializer,
    EquipmentSerializer
)

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# 1. Create Clinic (POST)
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
        try:
            serializer = ClinicSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            clinic = serializer.save()

            return Response(
                ClinicSerializer(clinic).data,
                status=status.HTTP_201_CREATED
            )

        except ValidationError as ve:
            logger.warning(f"Clinic validation failed: {ve.detail}")
            return Response({"error": ve.detail}, status=400)

        except Exception as e:
            logger.error("Unhandled Clinic Create Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=500)


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
            clinic = Clinic.objects.get(id=clinic_id)

            serializer = ClinicSerializer(clinic, data=request.data)
            serializer.is_valid(raise_exception=True)

            updated = serializer.save()

            return Response(
                ClinicSerializer(updated).data,
                status=status.HTTP_200_OK
            )

        except Clinic.DoesNotExist:
            logger.warning("Clinic not found")
            raise NotFound("Clinic not found")

        except ValidationError as ve:
            logger.warning(f"Clinic update validation failed: {ve.detail}")
            return Response({"error": ve.detail}, status=400)

        except Exception:
            logger.error("Unhandled Clinic Update Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=500)


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
            404: "Department or Equipment not found",
            500: "Internal Server Error"
        }
    )
    def put(self, request, department_id, equipment_id):
        try:
            logger.info(
                f"PUT Equipment | dep_id={department_id}, equipment_id={equipment_id}"
            )

            # 1 Validate Department
            department = Department.objects.get(id=department_id)

            # 2 Validate Equipment under Department
            equipment = Equipments.objects.filter(
                id=equipment_id,
                dep_id=department_id
            ).first()

            if not equipment:
                logger.warning("Equipment not found under department")
                raise NotFound("Equipment not found under this department")

            # 3 Validate & Save
            serializer = EquipmentSerializer(equipment, data=request.data)
            serializer.is_valid(raise_exception=True)

            updated_equipment = serializer.save()

            return Response(
                EquipmentSerializer(updated_equipment).data,
                status=status.HTTP_200_OK
            )

        except Department.DoesNotExist:
            logger.warning("Department not found")
            raise NotFound("Department not found")

        except ValidationError as ve:
            logger.warning(f"Equipment update validation failed: {ve.detail}")
            return Response({"error": ve.detail}, status=400)

        except NotFound:
            raise

        except Exception:
            logger.error("Unhandled Equipment Update Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=500)


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

