from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError, APIException
from drf_yasg.utils import swagger_auto_schema
import traceback
from .models import Clinic, Department, Equipments
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

        try:
            serializer = ClinicSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            clinic = serializer.save()

            return Response(
                ClinicSerializer(clinic).data,
                status=status.HTTP_201_CREATED
            )

        except ValidationError as ve:
            return Response({"error": ve.detail}, status=400)

        except Exception as e:
            logger.exception(f"Unhandled Clinic Create Error: {e}")
            return Response({"error": "Internal Server Error"}, status=500)



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

            serializer = ClinicSerializer(clinic, data=request.data)
            serializer.is_valid(raise_exception=True)

            updated = serializer.save()

            return Response(
                ClinicSerializer(updated).data,
                status=status.HTTP_200_OK
            )

        except Clinic.DoesNotExist:
            raise NotFound("Clinic not found")

        except ValidationError as ve:
            return Response({"error": ve.detail}, status=400)

        except Exception as e:
            logger.exception(f"Unhandled Clinic Update Error: {e}")
            return Response({"error": "Internal Server Error"}, status=500)



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

            serializer = ClinicReadSerializer(clinic)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Clinic.DoesNotExist:
            raise NotFound("Clinic not found")

        except Exception as e:
            logger.exception(f"Unhandled Clinic Fetch Error: {e}")
            return Response({"error": "Internal Server Error"}, status=500)



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

        try:
            department = Department.objects.get(id=department_id)

            serializer = EquipmentSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            equipment = serializer.save(dep=department)

            return Response(
                EquipmentSerializer(equipment).data,
                status=status.HTTP_201_CREATED
            )

        except Department.DoesNotExist:
            raise NotFound("Department not found")

        except ValidationError as ve:
            return Response({"error": ve.detail}, status=400)

        except Exception as e:
            logger.exception(f"Unhandled Equipment Create Error: {e}")
            return Response({"error": "Internal Server Error"}, status=500)



# -------------------------------------------------------------------
#  5. Update Equipment under Department (PUT)
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
            logger.info(f"PUT Request Received - dep_id={department_id}, eq_id={equipment_id}")

            # 1) Check department
            try:
                department = Department.objects.get(id=department_id)
                logger.info("Department found")
            except Department.DoesNotExist:
                logger.warning("Department NOT found")
                raise NotFound("Department not found")

            # 2) Check equipment under department
            equipment = Equipments.objects.filter(id=equipment_id, dep_id=department_id).first()
            if not equipment:
                logger.warning("Equipment NOT found under department")
                raise NotFound("Equipment not found under this department")

            logger.info("Equipment found under department, validating serializer...")

            # 3) Validate request data
            serializer = EquipmentSerializer(equipment, data=request.data)
            serializer.is_valid(raise_exception=True)

            logger.info("Serializer valid, saving...")

            updated_equipment = serializer.save()

            logger.info("Save success")

            return Response(EquipmentSerializer(updated_equipment).data, status=200)

        except ValidationError as ve:
            logger.error(f"ValidationError: {ve.detail}")
            return Response({"error": ve.detail}, status=400)

        except NotFound as nf:
            logger.warning(str(nf))
            raise nf  

        except Exception as e:
            logger.error("Unhandled Exception during update:\n" + traceback.format_exc())
            return Response({"error": " Internal Server Error"}, status=500)

