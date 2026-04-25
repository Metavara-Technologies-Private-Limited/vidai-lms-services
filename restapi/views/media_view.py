# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import logging
import mimetypes
import os
import traceback

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.utils._os import safe_join

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from restapi.utils.media import build_media_api_url

logger = logging.getLogger(__name__)


# =====================================================
# IMAGE UPLOAD API
# =====================================================
class ImageUploadAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        try:
            file = request.FILES.get("file")
            if not file:
                return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)
            path = default_storage.save(f"campaign_images/{file.name}", file)
            url = build_media_api_url(path)
            print(f"Image uploaded: {url} | path: {path}")
            return Response({"url": url, "path": path}, status=status.HTTP_200_OK)
        except Exception:
            logger.error("Image Upload Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MediaFileAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, path):
        normalized_path = str(path or "").strip().lstrip("/")
        if not normalized_path:
            raise Http404("File not found")

        try:
            file_path = safe_join(str(settings.MEDIA_ROOT), normalized_path)
        except Exception as exc:
            raise Http404("Invalid file path") from exc

        if not file_path or not os.path.isfile(file_path):
            raise Http404("File not found")

        content_type, _ = mimetypes.guess_type(file_path)
        response = FileResponse(
            open(file_path, "rb"),
            content_type=content_type or "application/octet-stream",
        )
        response["Cache-Control"] = "public, max-age=3600"
        return response
