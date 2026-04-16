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


# ==========================================
# 🔹 Referral Source List API
# ==========================================

class ReferralSourceListAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Get Referral Sources",
        operation_description="Fetch referral sources (Doctors, HR, Labs, etc.) with optional filters",
        manual_parameters=[
            openapi.Parameter(
                "type",
                openapi.IN_QUERY,
                description="Filter by type (doctor, corporate_hr, insurance, lab, partner)",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                "search",
                openapi.IN_QUERY,
                description="Search by referral source name",
                type=openapi.TYPE_STRING
            ),
        ],
        responses={
            200: openapi.Response(
                description="Referral sources fetched successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "success": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        "message": openapi.Schema(type=openapi.TYPE_STRING),
                        "count": openapi.Schema(type=openapi.TYPE_INTEGER),
                        "data": openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Items(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    "id": openapi.Schema(type=openapi.TYPE_INTEGER),
                                    "name": openapi.Schema(type=openapi.TYPE_STRING),
                                    "type": openapi.Schema(type=openapi.TYPE_STRING),
                                    "email": openapi.Schema(type=openapi.TYPE_STRING),
                                    "phone": openapi.Schema(type=openapi.TYPE_STRING),
                                    "clinic_name": openapi.Schema(type=openapi.TYPE_STRING),
                                    "referral_count": openapi.Schema(type=openapi.TYPE_INTEGER),
                                }
                            )
                        )
                    }
                )
            ),
            500: "Internal Server Error"
        }
    )
    def get(self, request):
        try:
            source_type = request.GET.get("type")
            search = request.GET.get("search")

            clinic = resolve_request_clinic(request, required=True)

            queryset = get_referral_sources(source_type, search, clinic)

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
        operation_description="Fetch count of referral sources grouped by type",
        responses={
            200: openapi.Response(
                description="Dashboard fetched successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "success": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        "message": openapi.Schema(type=openapi.TYPE_STRING),
                        "data": openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "doctor": openapi.Schema(type=openapi.TYPE_INTEGER),
                                "corporate_hr": openapi.Schema(type=openapi.TYPE_INTEGER),
                                "insurance": openapi.Schema(type=openapi.TYPE_INTEGER),
                                "lab": openapi.Schema(type=openapi.TYPE_INTEGER),
                                "partner": openapi.Schema(type=openapi.TYPE_INTEGER),
                            }
                        )
                    }
                )
            ),
            500: "Internal Server Error"
        }
    )
    def get(self, request):
        try:
            clinic = resolve_request_clinic(request, required=True)

            data = get_dashboard_counts(clinic)

            return Response({
                "success": True,
                "message": "Dashboard fetched successfully",
                "data": data
            })

        except Exception as e:
            return Response({
                "success": False,
                "message": str(e)
            }, status=500)