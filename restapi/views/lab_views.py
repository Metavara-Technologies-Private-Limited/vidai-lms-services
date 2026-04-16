# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError

from drf_yasg.utils import swagger_auto_schema

from restapi.models import Lab
from restapi.serializers.ticket_serializer import (
    LabWriteSerializer,
    LabReadSerializer,
)
from restapi.utils.clinic_scope import resolve_request_clinic



# -------------------------------------------------------------------
# LAB CREATE API
# -------------------------------------------------------------------
class LabCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create a new lab",
        request_body=LabWriteSerializer,
        responses={
            201: LabReadSerializer,
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Labs"],
    )
    def post(self, request):
        try:
            clinic = resolve_request_clinic(request, required=True)
            payload = request.data.copy()
            payload["clinic"] = clinic.id

            serializer = LabWriteSerializer(data=payload)
            serializer.is_valid(raise_exception=True)

            lab = serializer.save()

            return Response(
                LabReadSerializer(lab).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )


# -------------------------------------------------------------------
# LAB LIST API
# -------------------------------------------------------------------
class LabListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="List all active labs",
        responses={200: LabReadSerializer(many=True)},
        tags=["Labs"],
    )
    def get(self, request):
        clinic = resolve_request_clinic(request, required=True)

        labs = Lab.objects.filter(
            is_deleted=False,
            is_active=True,
            clinic=clinic,
        )

        return Response(
            LabReadSerializer(labs, many=True).data,
            status=status.HTTP_200_OK,
        )


# -------------------------------------------------------------------
# LAB UPDATE API
# -------------------------------------------------------------------
class LabUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Update lab",
        request_body=LabWriteSerializer,
        responses={
            200: LabReadSerializer,
            404: "Lab not found",
        },
        tags=["Labs"],
    )
    def put(self, request, lab_id):
        clinic = resolve_request_clinic(request, required=True)

        lab = get_object_or_404(
            Lab,
            id=lab_id,
            is_deleted=False,
            clinic=clinic,
        )

        payload = request.data.copy()
        payload["clinic"] = clinic.id

        serializer = LabWriteSerializer(
            lab,
            data=payload,
            partial=True
        )

        serializer.is_valid(raise_exception=True)

        updated_lab = serializer.save()

        return Response(
            LabReadSerializer(updated_lab).data,
            status=status.HTTP_200_OK,
        )


# -------------------------------------------------------------------
# LAB SOFT DELETE API
# -------------------------------------------------------------------
class LabSoftDeleteAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Soft delete lab",
        tags=["Labs"],
    )
    def delete(self, request, lab_id):
        clinic = resolve_request_clinic(request, required=True)

        lab = get_object_or_404(
            Lab,
            id=lab_id,
            is_deleted=False,
            clinic=clinic,
        )

        lab.is_deleted = True
        lab.is_active = False
        lab.save()

        return Response(
            {"message": "Lab deleted successfully"},
            status=status.HTTP_200_OK,
        )
