from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from restapi.services.report_service import (
    get_call_report,
    get_campaign_report,
    get_call_logs,
    get_campaign_metrics,
)

from restapi.serializers.reports_serializer import (
    CallLogSerializer,
    CampaignMetricsSerializer,
)


# =====================================================
# COMMON FILTER PARSER
# =====================================================
def get_filters(request):
    return {
        "clinic_id": request.GET.get("clinic_id"),
        "from_date": request.GET.get("from_date"),
        "to_date": request.GET.get("to_date"),
        "user_id": request.GET.get("user_id"),
        "platform": request.GET.get("platform"),
        "campaign_mode": request.GET.get("campaign_mode"),
    }


# =====================================================
# PAGINATION HELPER
# =====================================================
def paginate_queryset(queryset, request):
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 10))

    start = (page - 1) * page_size
    end = start + page_size

    total = queryset.count()
    data = queryset[start:end]

    return data, total


# =====================================================
# CALL REPORT VIEW
# =====================================================
class CallReportView(APIView):

    @swagger_auto_schema(
        operation_summary="Get Call Reports",
        operation_description="Fetch call KPIs and call logs with filters",
        manual_parameters=[
            openapi.Parameter("clinic_id", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("from_date", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="YYYY-MM-DD"),
            openapi.Parameter("to_date", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="YYYY-MM-DD"),
            openapi.Parameter("user_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("page_size", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
        ]
    )
    def get(self, request):
        try:
            filters = get_filters(request)

            # KPIs
            kpis = get_call_report(filters)

            # Table data
            queryset = get_call_logs(filters)
            paginated_data, total = paginate_queryset(queryset, request)

            serializer = CallLogSerializer(paginated_data, many=True)

            return Response({
                "success": True,
                "message": "Call report fetched successfully",
                "data": {
                    "kpis": kpis,
                    "records": serializer.data,
                    "pagination": {
                        "total": total,
                        "page": int(request.GET.get("page", 1)),
                        "page_size": int(request.GET.get("page_size", 10)),
                    }
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "success": False,
                "message": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


# =====================================================
# CAMPAIGN REPORT VIEW
# =====================================================
class CampaignReportView(APIView):

    @swagger_auto_schema(
        operation_summary="Get Campaign Reports",
        operation_description="Fetch campaign KPIs and metrics with filters",
        manual_parameters=[
            openapi.Parameter("clinic_id", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("from_date", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="YYYY-MM-DD"),
            openapi.Parameter("to_date", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="YYYY-MM-DD"),
            openapi.Parameter("platform", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="facebook / instagram / linkedin"),
            openapi.Parameter("campaign_mode", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="1=Organic, 2=Paid, 3=Email"),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("page_size", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
        ]
    )
    def get(self, request):
        try:
            filters = get_filters(request)

            # KPIs
            kpis = get_campaign_report(filters)

            # Table data
            queryset = get_campaign_metrics(filters)
            paginated_data, total = paginate_queryset(queryset, request)

            serializer = CampaignMetricsSerializer(paginated_data, many=True)

            return Response({
                "success": True,
                "message": "Campaign report fetched successfully",
                "data": {
                    "kpis": kpis,
                    "records": serializer.data,
                    "pagination": {
                        "total": total,
                        "page": int(request.GET.get("page", 1)),
                        "page_size": int(request.GET.get("page_size", 10)),
                    }
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "success": False,
                "message": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)