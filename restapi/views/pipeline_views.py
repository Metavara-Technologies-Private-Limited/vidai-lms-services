# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import logging
import traceback

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from restapi.models import Pipeline, PipelineStage
from restapi.serializers.pipeline_serializer import (
    PipelineSerializer,
    PipelineReadSerializer,
    PipelineStageReadSerializer,
)

from restapi.services.pipeline_service import (
    add_stage,
    update_stage,
    save_stage_rules,
    save_stage_fields,
    delete_stage,
    archive_stage,
    duplicate_stage,
)
from restapi.utils.clinic_scope import resolve_request_clinic

logger = logging.getLogger(__name__)


def _get_scoped_pipeline(request, pipeline_id):
    clinic = resolve_request_clinic(request, required=True)
    return Pipeline.objects.get(id=pipeline_id, clinic=clinic, is_deleted=False)


def _get_scoped_stage(request, stage_id):
    clinic = resolve_request_clinic(request, required=True)
    return PipelineStage.objects.get(id=stage_id, pipeline__clinic=clinic)




# -------------------------------------------------------------------
# Pipeline Create API View (POST)
# -------------------------------------------------------------------
class PipelineCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create a new sales pipeline",
        request_body=PipelineSerializer,
        responses={
            201: PipelineReadSerializer,
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Pipelines"],
    )
    def post(self, request):
        try:
            serializer = PipelineSerializer(
                data=request.data,
                context={"request": request},
            )
            serializer.is_valid(raise_exception=True)

            pipeline = serializer.save()

            return Response(
                PipelineReadSerializer(pipeline).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as ve:
            logger.warning(f"Pipeline validation failed: {ve.detail}")
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Pipeline Create Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# LIST PIPELINES (GET)
# -------------------------------------------------------------------
class PipelineListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="List all pipelines for a clinic",
        responses={200: PipelineReadSerializer(many=True)},
        tags=["Pipelines"],
    )
    def get(self, request):
        try:
            clinic = resolve_request_clinic(request, required=True)

            pipelines = Pipeline.objects.filter(
                clinic=clinic,
                is_active=True,
                is_deleted=False,
            )

            # ✅ INDUSTRY FILTER (CORRECT)
            industry = request.query_params.get("industry")
            if industry:
                pipelines = pipelines.filter(industry_type=industry)

            return Response(
                PipelineReadSerializer(
                    pipelines,
                    many=True,
                    context={"request": request},
                ).data,
                status=status.HTTP_200_OK,
            )

        except ValidationError as ve:
            return Response({"error": ve.detail}, status=status.HTTP_400_BAD_REQUEST)

        except Exception:
            logger.error("Unhandled Pipeline List Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# -------------------------------------------------------------------
# GET SINGLE PIPELINE (GET)
# -------------------------------------------------------------------
class PipelineDetailAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Get pipeline with stages, rules, and fields",
        responses={200: PipelineReadSerializer},
        tags=["Pipelines"],
    )
    def get(self, request, pipeline_id):
        try:
            pipeline = _get_scoped_pipeline(request, pipeline_id)

            return Response(
                PipelineReadSerializer(pipeline, context={"request": request}).data,
                status=status.HTTP_200_OK,
            )

        except Pipeline.DoesNotExist:
            return Response(
                {"error": "Pipeline not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except Exception:
            logger.error(
                "Unhandled Pipeline Detail Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        operation_description="Update pipeline",
        request_body=PipelineSerializer,
        responses={200: PipelineReadSerializer},
        tags=["Pipelines"],
    )
    def put(self, request, pipeline_id):
        try:
            pipeline = _get_scoped_pipeline(request, pipeline_id)
            serializer = PipelineSerializer(
                pipeline,
                data=request.data,
                context={"request": request},
                partial=True,
            )
            serializer.is_valid(raise_exception=True)
            updated = serializer.save()

            return Response(
                PipelineReadSerializer(updated, context={"request": request}).data,
                status=status.HTTP_200_OK,
            )

        except Pipeline.DoesNotExist:
            return Response(
                {"error": "Pipeline not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Pipeline Update Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request, pipeline_id):
        return self.put(request, pipeline_id)

    @swagger_auto_schema(
        operation_description="Delete pipeline",
        responses={200: openapi.Schema(type=openapi.TYPE_OBJECT)},
        tags=["Pipelines"],
    )
    def delete(self, request, pipeline_id):
        try:
            from restapi.services.pipeline_service import delete_pipeline

            _get_scoped_pipeline(request, pipeline_id)
            delete_pipeline(pipeline_id)

            return Response(
                {"message": "Pipeline deleted successfully"},
                status=status.HTTP_200_OK,
            )

        except Pipeline.DoesNotExist:
            return Response(
                {"error": "Pipeline not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Pipeline Detail DELETE Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# ADD STAGE TO PIPELINE (POST)
# -------------------------------------------------------------------
class PipelineStageCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Add a new stage to a pipeline",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "pipeline_id": openapi.Schema(type=openapi.TYPE_STRING),
                "stage_name": openapi.Schema(type=openapi.TYPE_STRING),
                "stage_type": openapi.Schema(type=openapi.TYPE_STRING),
            },
            required=["pipeline_id", "stage_name", "stage_type"],
        ),
        tags=["Pipeline Stages"],
    )
    def post(self, request):
        try:
            stage = add_stage(request.data)

            return Response(
                PipelineStageReadSerializer(stage, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Stage Create Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# UPDATE STAGE (PUT)
# -------------------------------------------------------------------
class PipelineStageUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Update pipeline stage",
        tags=["Pipeline Stages"],
    )
    def put(self, request, stage_id):
        try:
            stage = _get_scoped_stage(request, stage_id)
            stage = update_stage(stage, request.data)

            return Response(
                PipelineStageReadSerializer(stage, context={"request": request}).data,
                status=status.HTTP_200_OK,
            )

        except PipelineStage.DoesNotExist:
            return Response(
                {"error": "Stage not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Stage Update Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# SAVE STAGE RULES (POST)
# -------------------------------------------------------------------
class StageRuleSaveAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Save stage action rules",
        tags=["Pipeline Stages"],
    )
    def post(self, request, stage_id):
        try:
            stage = _get_scoped_stage(request, stage_id)
            save_stage_rules(stage, request.data.get("rules", []))

            return Response(
                {"message": "Stage rules saved"},
                status=status.HTTP_200_OK,
            )

        except PipelineStage.DoesNotExist:
            return Response(
                {"error": "Stage not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Stage Rule Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# SAVE STAGE FIELDS (POST)
# -------------------------------------------------------------------
class StageFieldSaveAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Save stage data capture fields",
        tags=["Pipeline Stages"],
    )
    def post(self, request, stage_id):
        try:
            stage = _get_scoped_stage(request, stage_id)
            save_stage_fields(stage, request.data.get("fields", []))

            return Response(
                {"message": "Stage fields saved"},
                status=status.HTTP_200_OK,
            )

        except PipelineStage.DoesNotExist:
            return Response(
                {"error": "Stage not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Stage Field Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# DUPLICATE PIPELINE (POST)
# -------------------------------------------------------------------
class PipelineDuplicateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Duplicate a pipeline with all stages and rules",
        responses={201: PipelineReadSerializer},
        tags=["Pipelines"],
    )
    def post(self, request, pipeline_id):
        try:
            from restapi.services.pipeline_service import duplicate_pipeline
            _get_scoped_pipeline(request, pipeline_id)
            new_pipeline = duplicate_pipeline(pipeline_id)
            return Response(
                PipelineReadSerializer(new_pipeline).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Pipeline Duplicate Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -------------------------------------------------------------------
# ARCHIVE PIPELINE (POST)
# -------------------------------------------------------------------
class PipelineArchiveAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Archive a pipeline (soft delete)",
        responses={200: PipelineReadSerializer},
        tags=["Pipelines"],
    )
    def post(self, request, pipeline_id):
        try:
            from restapi.services.pipeline_service import archive_pipeline
            _get_scoped_pipeline(request, pipeline_id)
            pipeline = archive_pipeline(pipeline_id)
            return Response(
                PipelineReadSerializer(pipeline).data,
                status=status.HTTP_200_OK,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Pipeline Archive Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -------------------------------------------------------------------
# DELETE PIPELINE (DELETE)
# -------------------------------------------------------------------
class PipelineDeleteAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Delete a pipeline permanently",
        responses={204: "No Content"},
        tags=["Pipelines"],
    )
    def delete(self, request, pipeline_id):
        try:
            from restapi.services.pipeline_service import delete_pipeline
            _get_scoped_pipeline(request, pipeline_id)
            delete_pipeline(pipeline_id)
            return Response(
                {"message": "Pipeline deleted successfully"},
                status=status.HTTP_200_OK,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Pipeline Delete Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request, pipeline_id):
        return self.delete(request, pipeline_id)


# -------------------------------------------------------------------
# DUPLICATE STAGE (POST)
# -------------------------------------------------------------------
class StageDuplicateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Duplicate a pipeline stage with all rules and fields",
        responses={201: openapi.Schema(type=openapi.TYPE_OBJECT)},
        tags=["Pipeline Stages"],
    )
    def post(self, request, stage_id):
        try:
            _get_scoped_stage(request, stage_id)
            new_stage = duplicate_stage(stage_id)
            return Response(
                PipelineStageReadSerializer(new_stage, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Stage Duplicate Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -------------------------------------------------------------------
# ARCHIVE STAGE (POST)
# -------------------------------------------------------------------
class StageArchiveAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Archive a pipeline stage (soft delete)",
        responses={200: openapi.Schema(type=openapi.TYPE_OBJECT)},
        tags=["Pipeline Stages"],
    )
    def put(self, request, stage_id):
        try:
            _get_scoped_stage(request, stage_id)
            stage = archive_stage(stage_id)
            return Response(
                PipelineStageReadSerializer(stage, context={"request": request}).data,
                status=status.HTTP_200_OK,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Stage Archive Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request, stage_id):
        return self.put(request, stage_id)


# -------------------------------------------------------------------
# DELETE STAGE (DELETE)
# -------------------------------------------------------------------
class StageDeleteAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Delete a pipeline stage permanently",
        responses={204: "No Content"},
        tags=["Pipeline Stages"],
    )
    def delete(self, request, stage_id):
        try:
            _get_scoped_stage(request, stage_id)
            delete_stage(stage_id)
            return Response(
                {"message": "Stage deleted successfully"},
                status=status.HTTP_200_OK,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Stage Delete Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request, stage_id):
        return self.delete(request, stage_id)


# -------------------------------------------------------------------
# STAGE DETAIL / FALLBACK UPDATE+DELETE (PUT, DELETE)
# -------------------------------------------------------------------
class StageDetailAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Fallback update endpoint for pipeline stage",
        tags=["Pipeline Stages"],
    )
    def put(self, request, stage_id):
        try:
            stage = _get_scoped_stage(request, stage_id)
            stage = update_stage(stage, request.data)

            return Response(
                PipelineStageReadSerializer(stage, context={"request": request}).data,
                status=status.HTTP_200_OK,
            )

        except PipelineStage.DoesNotExist:
            return Response(
                {"error": "Stage not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Stage Detail PUT Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request, stage_id):
        return self.put(request, stage_id)

    @swagger_auto_schema(
        operation_description="Fallback delete endpoint for pipeline stage",
        tags=["Pipeline Stages"],
    )
    def delete(self, request, stage_id):
        try:
            _get_scoped_stage(request, stage_id)
            delete_stage(stage_id)
            return Response(status=status.HTTP_204_NO_CONTENT)

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Stage Detail DELETE Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
CAMPAIGN_OBJECTIVES = {
    "awareness": "Brand Awareness",
    "leads": "Lead Generation",
}


# -------------------------------------------------------------------
# ✅ NEW REQUIRED API → GET STAGES BY PIPELINE
# -------------------------------------------------------------------
class PipelineStagesListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Get all stages for a pipeline",
        responses={200: PipelineStageReadSerializer(many=True)},  # ✅ FIX
        tags=["Pipeline Stages"],
    )
    def get(self, request, pipeline_id):
        try:
            pipeline = _get_scoped_pipeline(request, pipeline_id)

            stages = PipelineStage.objects.filter(
                pipeline=pipeline,
                is_deleted=False,
                is_active=True
            ).order_by("stage_order")

            return Response(
                PipelineStageReadSerializer(
                    stages,
                    many=True,
                    context={"request": request}
                ).data,
                status=status.HTTP_200_OK
            )

        except Pipeline.DoesNotExist:
            return Response(
                {"error": "Pipeline not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        except Exception:
            logger.error("Stage List Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )