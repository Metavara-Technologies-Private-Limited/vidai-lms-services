# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import logging
import traceback

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from drf_yasg.utils import swagger_auto_schema

from restapi.models import LeadNote
from restapi.serializers.lead_note_serializers import (
    LeadNoteSerializer,
    LeadNoteReadSerializer
)
from restapi.services.lead_note_service import delete_lead_note

logger = logging.getLogger(__name__)




# =====================================================
# CREATE LEAD NOTE API
# =====================================================
class LeadNoteCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create a new note for a Lead",
        request_body=LeadNoteSerializer,
        responses={
            201: LeadNoteReadSerializer,
            400: "Validation Error",
            500: "Internal Server Error",
        },
    )
    def post(self, request):
        try:
            serializer = LeadNoteSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            note = serializer.save()

            return Response(
                LeadNoteReadSerializer(note).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as validation_error:
            logger.warning(f"Lead Note Create validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Lead Note Create Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================
# UPDATE LEAD NOTE API
# =====================================================
class LeadNoteUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Update an existing Lead note",
        request_body=LeadNoteSerializer,
        responses={
            200: LeadNoteReadSerializer,
            400: "Validation Error",
            404: "Not Found",
            500: "Internal Server Error",
        },
    )
    def put(self, request, note_id):
        try:
            note_instance = LeadNote.objects.filter(
                id=note_id,
                is_deleted=False
            ).first()

            if not note_instance:
                return Response(
                    {"error": "Lead note not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = LeadNoteSerializer(
                note_instance,
                data=request.data,
                partial=True
            )

            serializer.is_valid(raise_exception=True)
            updated_note = serializer.save()

            return Response(
                LeadNoteReadSerializer(updated_note).data,
                status=status.HTTP_200_OK,
            )

        except ValidationError as validation_error:
            logger.warning(
                f"Lead Note Update validation failed: {validation_error.detail}"
            )
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Lead Note Update Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================
# DELETE LEAD NOTE API (SOFT DELETE)
# =====================================================
class LeadNoteDeleteAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Soft delete a Lead note",
        responses={
            200: "Deleted Successfully",
            404: "Not Found",
            500: "Internal Server Error",
        },
    )
    def delete(self, request, note_id):
        try:
            note_instance = LeadNote.objects.filter(
                id=note_id,
                is_deleted=False
            ).first()

            if not note_instance:
                return Response(
                    {"error": "Lead note not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            delete_lead_note(note_instance)

            return Response(
                {"message": "Lead note deleted successfully."},
                status=status.HTTP_200_OK,
            )

        except ValidationError as validation_error:
            logger.warning(f"Lead Note Delete validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Lead Note Delete Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================
# LIST NOTES BY LEAD API
# =====================================================
class LeadNoteListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="List all notes for a specific Lead",
        responses={
            200: LeadNoteReadSerializer(many=True),
            500: "Internal Server Error",
        },
    )
    def get(self, request, lead_id):
        try:
            notes = LeadNote.objects.filter(
                lead_id=lead_id,
                is_deleted=False
            ).order_by("-created_at")

            serializer = LeadNoteReadSerializer(notes, many=True)

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Lead Note List Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )