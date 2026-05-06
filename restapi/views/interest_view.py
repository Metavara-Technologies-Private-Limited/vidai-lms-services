import logging
import traceback

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from drf_yasg.utils import swagger_auto_schema

from restapi.models import Interest, Clinic
from restapi.serializers.interest_serializer import InterestSerializer

logger = logging.getLogger(__name__)


# =========================================================
# CREATE INTEREST
# =========================================================
class InterestCreateAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Create a new Interest",
        request_body=InterestSerializer,
        responses={
            201: InterestSerializer,
            400: "Validation Error",
            500: "Internal Server Error"
        },
        tags=["Interest"],
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

            serializer = InterestSerializer(
                data=request.data,
                context={"request": request}
            )

            serializer.is_valid(raise_exception=True)

            interest = serializer.save(clinic=clinic)

            return Response(
                InterestSerializer(interest).data,
                status=201
            )

        except ValidationError as ve:
            return Response({"error": ve.detail}, status=400)

        except Exception:
            logger.error(
                "Unhandled Interest Create Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=500
            )


# =========================================================
# LIST INTERESTS
# =========================================================
class InterestListAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get all Interests for a clinic",
        responses={200: InterestSerializer(many=True)},
        tags=["Interest"],
    )
    def get(self, request):

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

            interests = Interest.objects.filter(
                clinic=clinic,
                is_active=True
            ).order_by("name")

            return Response(
                InterestSerializer(interests, many=True).data
            )

        except ValidationError as ve:
            return Response({"error": ve.detail}, status=400)

        except Exception:
            logger.error(
                "Interest List Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=500
            )


# =========================================================
# UPDATE INTEREST
# =========================================================
class InterestUpdateAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Update Interest",
        request_body=InterestSerializer,
        responses={200: InterestSerializer},
        tags=["Interest"],
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

            interest = Interest.objects.filter(
                id=pk,
                clinic=clinic,
                is_active=True
            ).first()

            if not interest:
                return Response(
                    {"error": "Interest not found"},
                    status=404
                )

            serializer = InterestSerializer(
                interest,
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
                "Interest Update Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=500
            )


