from django.contrib import admin
from django.urls import path, include

# Swagger Imports
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

from django.http import JsonResponse
from django.urls import path, include

# Swagger Configuration
schema_view = get_schema_view(
    openapi.Info(
        title="Clinic API Documentation",
        default_version="v1",
        description="API documentation",
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("restapi.urls")),

    # Swagger UI
    path("swagger/", schema_view.with_ui("swagger", cache_timeout=0)),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0)),

    path("", lambda request: JsonResponse({"status": "LMS backend running"})),
]
