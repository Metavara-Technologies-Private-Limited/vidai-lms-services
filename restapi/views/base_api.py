from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from restapi.services.permission_service import has_permission, filter_by_clinic


class BaseAPIView(APIView):

    module = None
    category = None

    def check_permission(self, request, action):
        if not has_permission(request.user, self.module, self.category, action):
            return Response({
                "success": False,
                "message": "Permission denied"
            }, status=status.HTTP_403_FORBIDDEN)
        return None

    def get_filtered_queryset(self, queryset):
        return filter_by_clinic(queryset, self.request.user)