# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
from django.shortcuts import get_object_or_404
from django.db.models import Avg

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from restapi.models.reputation import ReviewRequest, Review, ReviewRequestLead
from restapi.serializers.reputation_serializer import (
    ReviewRequestSerializer,
    ReviewSerializer,
)

# =====================================================
# =====================================================
# REPUTATION MANAGEMENT - CREATE REVIEW REQUEST
# POST /api/reputation/review-request/

class ReviewRequestCreateAPIView(APIView):

    def post(self, request):

        serializer = ReviewRequestSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        review_request = serializer.save()
        delivery_report = getattr(review_request, "_delivery_report", None)

        response_status = "success"
        response_message = "Review request created"

        if delivery_report and delivery_report.get("failed_count"):
            if delivery_report.get("success_count"):
                response_status = "partial_success"
                response_message = "Review request created with some delivery failures"
            else:
                response_status = "error"
                response_message = "Review request created but no messages were delivered"

        return Response(
            {
                "status": response_status,
                "message": response_message,
                "data": serializer.data,
                "delivery_report": delivery_report,
            },
            status=status.HTTP_201_CREATED
        )

# REPUTATION MANAGEMENT - LIST REVIEW REQUESTS  
# GET /api/reputation/review-requests/
class ReviewRequestListAPIView(APIView):

    def get(self, request):

        review_requests = ReviewRequest.objects.all().prefetch_related("leads", "reviews").order_by("-created_at")

        serializer = ReviewRequestSerializer(review_requests, many=True)

        return Response(
            {
                "status": "success",
                "data": serializer.data
            }
        )

# REPUTATION MANAGEMENT - REVIEW REQUEST DETAIL 
# GET /api/reputation/review-request/<request_id>/

class ReviewRequestDetailAPIView(APIView):

    def get(self, request, request_id):

        review_request = get_object_or_404(
            ReviewRequest.objects.prefetch_related("leads", "reviews"),
            id=request_id,
        )

        serializer = ReviewRequestSerializer(review_request)

        return Response(
            {
                "status": "success",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

# REPUTATION MANAGEMENT - LIST REVIEWS FOR A REQUEST
# GET /api/reputation/review-request/<request_id>/reviews/
class ReviewListAPIView(APIView):
    def get(self, request, request_id):

        reviews = Review.objects.filter(review_request_id=request_id)

        serializer = ReviewSerializer(reviews, many=True)

        return Response(
            {
                "status": "success",
                "data": serializer.data
            }
        )

# REPUTATION MANAGEMENT - SUBMIT REVIEW
# POST /api/reputation/submit-review/
class ReviewCreateAPIView(APIView):

    def post(self, request):

        serializer = ReviewSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()

            ReviewRequestLead.objects.filter(
                review_request_id=serializer.instance.review_request_id,
                lead_id=serializer.instance.lead_id,
            ).update(review_submitted=True)

            return Response(
                {
                    "status": "success",
                    "message": "Review submitted successfully",
                    "data": serializer.data
                },
                status=status.HTTP_201_CREATED
            )

        return Response(
            {
                "status": "error",
                "errors": serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )

# REPUTATION MANAGEMENT - DASHBOARD INSIGHTS
# GET /api/reputation/dashboard/
class ReputationDashboardAPIView(APIView):

    def get(self, request):

        from django.db.models import Avg
        from restapi.models.reputation import ReviewRequest, Review, ReviewRequestLead

        total_requests = ReviewRequest.objects.count()
        total_sent_requests = ReviewRequestLead.objects.filter(request_sent=True).count()

        total_reviews = Review.objects.count()

        avg_rating = Review.objects.aggregate(
            avg_rating=Avg("rating")
        )["avg_rating"] or 0

        conversion_rate = 0
        if total_sent_requests > 0:
            conversion_rate = (total_reviews / total_sent_requests) * 100

        return Response(
            {
                "avg_rating": round(avg_rating, 1),
                "requests_sent": total_sent_requests,
                "reviews_submitted": total_reviews,
                "total_reviews": total_reviews,
                "total_requests": total_requests,
                "conversion_rate": round(conversion_rate, 1),
            }
        )
