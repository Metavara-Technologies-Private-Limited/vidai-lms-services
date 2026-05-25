import logging
import traceback
from typing import Optional

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from drf_yasg.utils import swagger_auto_schema

from restapi.models import UseCase, Clinic
from restapi.serializers.usecase_serializer import UseCaseSerializer

logger = logging.getLogger(__name__)


DEFAULT_TEMPLATE_USE_CASE_NAMES = [
    "Follow-Up",
    "Reminder",
    "Re-engagement",
    "Feedback",
    "No-Show",
    "Appointment",
]


def normalize_use_case_name(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def resolve_clinic_from_request(request) -> Clinic:
    clinic_id = request.query_params.get("clinic_id") or request.data.get("clinic_id")

    if not clinic_id:
        raise ValidationError({"clinic": "clinic_id required"})

    clinic = Clinic.objects.filter(id=clinic_id).first()

    if not clinic:
        raise ValidationError({
            "clinic": "Invalid clinic"
        })

    return clinic


def ensure_default_use_cases(clinic: Clinic) -> None:
    existing = UseCase.objects.filter(clinic=clinic)
    existing_by_normalized = {
        normalize_use_case_name(item.name): item
        for item in existing
    }

    for default_name in DEFAULT_TEMPLATE_USE_CASE_NAMES:
        key = normalize_use_case_name(default_name)
        matched: Optional[UseCase] = existing_by_normalized.get(key)

        if matched:
            if not matched.is_active:
                matched.is_active = True
                matched.name = default_name
                matched.save(update_fields=["is_active", "name"])
            continue

        UseCase.objects.create(
            clinic=clinic,
            name=default_name,
            is_active=True,
        )


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
            clinic = resolve_clinic_from_request(request)
            request.clinic = clinic

            incoming_name = str(request.data.get("name", "")).strip()
            if incoming_name:
                inactive_match = UseCase.objects.filter(
                    clinic=clinic,
                    name__iexact=incoming_name,
                    is_active=False,
                ).first()
                if inactive_match:
                    inactive_match.name = incoming_name
                    inactive_match.is_active = True
                    inactive_match.save(update_fields=["name", "is_active"])
                    return Response(UseCaseSerializer(inactive_match).data, status=201)

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
            clinic = resolve_clinic_from_request(request)
            request.clinic = clinic

            ensure_default_use_cases(clinic)

            usecases = UseCase.objects.filter(
                clinic=clinic,
                is_active=True
            )

            priority = {
                normalize_use_case_name(name): index
                for index, name in enumerate(DEFAULT_TEMPLATE_USE_CASE_NAMES)
            }

            usecases = sorted(
                usecases,
                key=lambda item: (
                    priority.get(normalize_use_case_name(item.name), 99),
                    item.name.lower(),
                ),
            )

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
            clinic = resolve_clinic_from_request(request)
            request.clinic = clinic

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
