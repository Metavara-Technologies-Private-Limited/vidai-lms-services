# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import logging
import traceback

from django.conf import settings
from django.core.files.storage import default_storage

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser

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
            from django.core.files.storage import default_storage
            path = default_storage.save(f"campaign_images/{file.name}", file)
            url = request.build_absolute_uri(settings.MEDIA_URL + path)
            print(f"Image uploaded: {url} | path: {path}")
            return Response({"url": url, "path": path}, status=status.HTTP_200_OK)
        except Exception:
            logger.error("Image Upload Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
