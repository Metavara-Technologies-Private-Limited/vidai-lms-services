from django.contrib import admin
from django.urls import path, include

# Swagger Imports
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

#  Swagger Configuration
schema_view = get_schema_view(
    openapi.Info(
        title="Clinic API Documentation",
        default_version='v1',
        description="API documentation for Clinic, Department, and Equipment",
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('restapi.urls')),

    #  Swagger UI Routes
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='redoc'),
]

#  Static files support (REQUIRED FOR SWAGGER CSS/JS)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
