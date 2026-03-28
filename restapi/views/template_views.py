# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import logging
import traceback

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, FormParser

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from restapi.models import (
    TemplateMail,
    TemplateSMS,
    TemplateWhatsApp,
    TemplateMailDocument,
    TemplateSMSDocument,
    TemplateWhatsAppDocument,
)

from restapi.serializers.template_serializers import (
    TemplateMailSerializer,
    TemplateSMSSerializer,
    TemplateWhatsAppSerializer,
    TemplateMailReadSerializer,
    TemplateSMSReadSerializer,
    TemplateWhatsAppReadSerializer,
)

logger = logging.getLogger(__name__)



# -------------------------------------------------------------------
# TEMPLATE LIST API (GET)
# -------------------------------------------------------------------
class TemplateListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="List Templates by type (mail, sms, whatsapp)",
    )
    def get(self, request, template_type):
        try:
            if template_type == "mail":
                templates = TemplateMail.objects.filter(is_deleted=False)
                serializer = TemplateMailReadSerializer(templates, many=True)

            elif template_type == "sms":
                templates = TemplateSMS.objects.filter(is_deleted=False)
                serializer = TemplateSMSReadSerializer(templates, many=True)

            elif template_type == "whatsapp":
                templates = TemplateWhatsApp.objects.filter(is_deleted=False)
                serializer = TemplateWhatsAppReadSerializer(templates, many=True)

            else:
                raise ValidationError(
                    "Invalid template type. Allowed values: mail, sms, whatsapp."
                )

            return Response(serializer.data, status=status.HTTP_200_OK)

        except ValidationError as validation_error:
            logger.warning(f"Template List validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Template List Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -------------------------------------------------------------------
# TEMPLATE DETAIL API (GET)
# -------------------------------------------------------------------
class TemplateDetailAPIView(APIView):

    def get(self, request, template_type, template_id):
        try:

            if template_type == "mail":
                template_instance = TemplateMail.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "Mail template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                serializer = TemplateMailReadSerializer(template_instance)

            elif template_type == "sms":
                template_instance = TemplateSMS.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "SMS template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                serializer = TemplateSMSReadSerializer(template_instance)

            elif template_type == "whatsapp":
                template_instance = TemplateWhatsApp.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "WhatsApp template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                serializer = TemplateWhatsAppReadSerializer(template_instance)

            else:
                raise ValidationError(
                    "Invalid template type. Allowed values: mail, sms, whatsapp."
                )

            return Response(serializer.data, status=status.HTTP_200_OK)

        except ValidationError as validation_error:
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# TEMPLATE CREATE API (POST)
# -------------------------------------------------------------------
class TemplateCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create Template (mail, sms, whatsapp)",
    )
    def post(self, request, template_type):
        try:
            if template_type == "mail":
                write_serializer = TemplateMailSerializer(data=request.data)
                read_serializer_class = TemplateMailReadSerializer

            elif template_type == "sms":
                write_serializer = TemplateSMSSerializer(data=request.data)
                read_serializer_class = TemplateSMSReadSerializer

            elif template_type == "whatsapp":
                write_serializer = TemplateWhatsAppSerializer(data=request.data)
                read_serializer_class = TemplateWhatsAppReadSerializer

            else:
                raise ValidationError(
                    "Invalid template type. Allowed values: mail, sms, whatsapp."
                )

            write_serializer.is_valid(raise_exception=True)
            template_instance = write_serializer.save()

            return Response(
                read_serializer_class(template_instance).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as validation_error:
            logger.warning(f"Template Create validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Template Create Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# TEMPLATE UPDATE API (PUT)
# -------------------------------------------------------------------
class TemplateUpdateAPIView(APIView):

    def put(self, request, template_type, template_id):
        try:
            if template_type == "mail":
                template_instance = TemplateMail.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "Mail template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                serializer = TemplateMailSerializer(
                    template_instance,
                    data=request.data,
                    partial=True
                )

                read_serializer_class = TemplateMailReadSerializer

            elif template_type == "sms":
                template_instance = TemplateSMS.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "SMS template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                serializer = TemplateSMSSerializer(
                    template_instance,
                    data=request.data,
                    partial=True
                )

                read_serializer_class = TemplateSMSReadSerializer

            elif template_type == "whatsapp":
                template_instance = TemplateWhatsApp.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "WhatsApp template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                serializer = TemplateWhatsAppSerializer(
                    template_instance,
                    data=request.data,
                    partial=True
                )

                read_serializer_class = TemplateWhatsAppReadSerializer

            else:
                raise ValidationError(
                    "Invalid template type. Allowed values: mail, sms, whatsapp."
                )

            serializer.is_valid(raise_exception=True)
            updated_template = serializer.save()

            return Response(
                read_serializer_class(updated_template).data,
                status=status.HTTP_200_OK,
            )

        except ValidationError as validation_error:
            logger.warning(f"Template Update validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Template Update Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# TEMPLATE DOCUMENT UPLOAD API (POST)
# -------------------------------------------------------------------
class TemplateDocumentUploadAPIView(APIView):

    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        operation_description="Upload a document to a template (mail, sms, whatsapp)",
        manual_parameters=[
            openapi.Parameter(
                name="file",
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True,
                description="The file to upload"
            )
        ],
        responses={
            201: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "id": openapi.Schema(type=openapi.TYPE_STRING),
                    "file": openapi.Schema(type=openapi.TYPE_STRING),
                    "uploaded_at": openapi.Schema(type=openapi.TYPE_STRING),
                    "template_id": openapi.Schema(type=openapi.TYPE_STRING),
                },
            ),
            400: "Validation Error",
            404: "Template Not Found",
            500: "Internal Server Error",
        },
        tags=["Templates"],
    )
    def post(self, request, template_type, template_id):

        if getattr(self, "swagger_fake_view", False):
            return Response(status=200)

        try:
            if template_type == "mail":
                template_instance = TemplateMail.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "Mail template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                DocumentModel = TemplateMailDocument

            elif template_type == "sms":
                template_instance = TemplateSMS.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "SMS template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                DocumentModel = TemplateSMSDocument

            elif template_type == "whatsapp":
                template_instance = TemplateWhatsApp.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "WhatsApp template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                DocumentModel = TemplateWhatsAppDocument

            else:
                return Response(
                    {"error": "Invalid template type. Allowed values: mail, sms, whatsapp."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            uploaded_file = request.FILES.get("file")

            if not uploaded_file:
                return Response(
                    {"error": "No file was submitted. Send the file under the key 'file'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            document = DocumentModel.objects.create(
                template=template_instance,
                file=uploaded_file,
            )

            logger.info(
                f"Template document uploaded: type={template_type}, "
                f"template_id={template_id}, doc_id={document.id}, "
                f"file={uploaded_file.name}"
            )

            return Response(
                {
                    "id": str(document.id),
                    "file": document.file.url if document.file else None,
                    "uploaded_at": document.uploaded_at.isoformat() if hasattr(document, 'uploaded_at') else None,
                    "template_id": str(template_id),
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception:
            logger.error(
                "Template Document Upload Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# TEMPLATE SOFT DELETE API (DELETE)
# -------------------------------------------------------------------
class TemplateDeleteAPIView(APIView):

    def delete(self, request, template_type, template_id):
        try:
            if template_type == "mail":
                template_instance = TemplateMail.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

            elif template_type == "sms":
                template_instance = TemplateSMS.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

            elif template_type == "whatsapp":
                template_instance = TemplateWhatsApp.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

            else:
                raise ValidationError(
                    "Invalid template type. Allowed values: mail, sms, whatsapp."
                )

            if not template_instance:
                return Response(
                    {"error": "Template not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            template_instance.is_deleted = True
            template_instance.save()

            return Response(
                {"message": "Template deleted successfully."},
                status=status.HTTP_200_OK,
            )

        except ValidationError as validation_error:
            logger.warning(f"Template Delete validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Template Delete Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
