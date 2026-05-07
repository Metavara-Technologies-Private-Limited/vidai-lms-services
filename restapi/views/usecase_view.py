import logging
import traceback

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from drf_yasg.utils import swagger_auto_schema

from restapi.models import UseCase, Clinic
from restapi.serializers.usecase_serializer import UseCaseSerializer

logger = logging.getLogger(__name__)


# =========================================================
# CREATE USECASE
# =========================================================
class UseCaseCreateAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Create a new Use Case",
        request_body=UseCaseSerializer,
        responses={
            201: UseCaseSerializer,
            400: "Validation Error",
            500: "Internal Server Error"
        },
        tags=["UseCase"],
    )
    def post(self, request):

        try:
            clinic_id = request.headers.get("X-Clinic-Id")

            if not clinic_id:
                raise ValidationError({
                    "clinic": "X-Clinic-Id header required"
                })

            clinic = Clinic.objects.filter(id=clinic_id).first()

            if not clinic:
                raise ValidationError({
                    "clinic": "Invalid clinic"
                })

            serializer = UseCaseSerializer(
                data=request.data,
                context={"request": request}
            )

            serializer.is_valid(raise_exception=True)

            usecase = serializer.save(clinic=clinic)

            return Response(
                UseCaseSerializer(usecase).data,
                status=201
            )

        except ValidationError as ve:
            return Response({"error": ve.detail}, status=400)

        except Exception:
            logger.error(
                "Unhandled UseCase Create Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=500
            )


# =========================================================
# LIST USECASES
# =========================================================
class UseCaseListAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get all Use Cases for a clinic",
        responses={200: UseCaseSerializer(many=True)},
        tags=["UseCase"],
    )
    def get(self, request):

        try:
            clinic_id = request.query_params.get(
                "clinic_id"
            )

            if not clinic_id:
                raise ValidationError({
                    "clinic": "X-Clinic-Id header required"
                })

            clinic = Clinic.objects.filter(id=clinic_id).first()

            if not clinic:
                raise ValidationError({
                    "clinic": "Invalid clinic"
                })

            usecases = UseCase.objects.filter(
                clinic=clinic,
                is_active=True
            ).order_by("name")

            return Response(
                UseCaseSerializer(usecases, many=True).data
            )

        except ValidationError as ve:
            return Response({"error": ve.detail}, status=400)

        except Exception:
            logger.error(
                "UseCase List Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=500
            )


# =========================================================
# UPDATE USECASE
# =========================================================
class UseCaseUpdateAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Update Use Case",
        request_body=UseCaseSerializer,
        responses={200: UseCaseSerializer},
        tags=["UseCase"],
    )
    def put(self, request, pk):

        try:
            clinic_id = request.headers.get("X-Clinic-Id")

            if not clinic_id:
                raise ValidationError({
                    "clinic": "X-Clinic-Id header required"
                })

            clinic = Clinic.objects.filter(id=clinic_id).first()

            if not clinic:
                raise ValidationError({
                    "clinic": "Invalid clinic"
                })

            usecase = UseCase.objects.filter(
                id=pk,
                clinic=clinic,
                is_active=True
            ).first()

            if not usecase:
                return Response(
                    {"error": "UseCase not found"},
                    status=404
                )

            serializer = UseCaseSerializer(
                usecase,
                data=request.data,
                partial=True,
                context={"request": request}
            )

            serializer.is_valid(raise_exception=True)
            serializer.save()

            return Response(serializer.data)

        except ValidationError as ve:
            return Response({"error": ve.detail}, status=400)

        except Exception:
            logger.error(
                "UseCase Update Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=500
            )
