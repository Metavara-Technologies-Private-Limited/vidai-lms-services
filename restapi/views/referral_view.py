# restapi/views/referral_view.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from restapi.services.referral_service import (
    get_referral_sources,
    get_dashboard_counts
)
from restapi.serializers.referral_serializer import ReferralSourceSerializer
from restapi.utils.clinic_scope import resolve_request_clinic
from restapi.models import Lead, ReferralDepartment

# ==========================================
# 🔹 Referral Source List API
# ==========================================

class ReferralSourceListAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Get Referral Sources",
        operation_description="Fetch referral sources with filters",
        manual_parameters=[
            openapi.Parameter(
                "search",
                openapi.IN_QUERY,
                description="Search by name",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                "referral_department_id",
                openapi.IN_QUERY,
                description="Filter by referral department",
                type=openapi.TYPE_INTEGER
            ),
        ],
    )
    def get(self, request):
        try:
            search = request.GET.get("search")
            department_id = request.GET.get("referral_department_id")

            # 🔥 CLINIC ISOLATION (STRICT)
            clinic = resolve_request_clinic(request, required=True)

            queryset = get_referral_sources(
                department_id=department_id,
                search=search,
                clinic=clinic
            )

            serializer = ReferralSourceSerializer(queryset, many=True)

            return Response({
                "success": True,
                "message": "Referral sources fetched successfully",
                "count": len(serializer.data),
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "success": False,
                "message": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# 🔹 Referral Dashboard API
# ==========================================

class ReferralDashboardAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Get Referral Dashboard Counts",
        operation_description="Fetch count of referral sources grouped by type"
    )
    def get(self, request):
        try:
            clinic = resolve_request_clinic(request, required=True)

            counts = {}

            departments = ReferralDepartment.objects.filter(
                clinic=clinic,
                is_active=True
            )

            for dept in departments:
                count = Lead.objects.filter(
                    clinic=clinic,
                    referral_department=dept,
                    is_deleted=False
                ).values("referral_source_id").distinct().count()

                counts[dept.name] = count

            return Response({
                "success": True,
                "message": "Dashboard fetched successfully",
                "data": counts
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "success": False,
                "message": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# 🔹 Referral Department List API
# ==========================================

class ReferralDepartmentListAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Get Referral Departments",
        operation_description="Fetch referral departments for dropdown"
    )
    def get(self, request):
        try:
            # 🔥 CLINIC ISOLATION
            clinic = resolve_request_clinic(request, required=True)

            departments = ReferralDepartment.objects.filter(
                clinic=clinic,
                is_active=True
            ).only("id", "name").order_by("name")   # 🔥 OPTIMIZED

            data = [
                {
                    "id": dept.id,
                    "name": dept.name
                }
                for dept in departments
            ]

            return Response({
                "success": True,
                "data": data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "success": False,
                "message": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)