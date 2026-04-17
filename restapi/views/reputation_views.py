# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
from django.shortcuts import get_object_or_404
from django.db.models import Avg

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

import logging

from restapi.models.reputation import ReviewRequest, Review, ReviewRequestLead
from restapi.serializers.reputation_serializer import (
    ReviewRequestSerializer,
    ReviewSerializer,
)
from restapi.utils.clinic_scope import resolve_request_clinic

logger = logging.getLogger(__name__)

# =====================================================
# =====================================================
# REPUTATION MANAGEMENT - CREATE REVIEW REQUEST
# POST /api/reputation/review-request/

class ReviewRequestCreateAPIView(APIView):

    def post(self, request):
        clinic = resolve_request_clinic(request, required=True)
        payload = request.data.copy()
        payload["clinic"] = clinic.id

        serializer = ReviewRequestSerializer(data=payload)

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
        clinic = resolve_request_clinic(request, required=True)
        review_requests = (
            ReviewRequest.objects
            .filter(clinic=clinic)
            .prefetch_related("leads", "reviews")
            .order_by("-created_at")
        )

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
        clinic = resolve_request_clinic(request, required=True)

        review_request = get_object_or_404(
            ReviewRequest.objects.prefetch_related("leads", "reviews"),
            id=request_id,
            clinic=clinic,
        )

        serializer = ReviewRequestSerializer(review_request)

        return Response(
            {
                "status": "success",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

# =====================================================
# PUBLIC ENDPOINT — No auth required
# Used by ReviewForm page when a lead opens the review link in their email
# GET /api/reputation/public/requests/<request_id>/
# =====================================================
class ReviewRequestPublicDetailAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, request_id):
        lead_id = request.query_params.get("lead") or request.query_params.get("lead_id")

        review_request = ReviewRequest.objects.filter(id=request_id).first()

        if not review_request:
            logger.warning("Public review request not found | request_id=%s", request_id)
            return Response(
                {
                    "status": "error",
                    "message": "Invalid or expired review link",
                    "request_id": str(request_id),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        request_lead = None
        if lead_id:
            request_lead = ReviewRequestLead.objects.select_related("lead").filter(
                review_request_id=review_request.id,
                lead_id=lead_id,
            ).first()

            if not request_lead:
                logger.warning(
                    "Public review request lead not found | request_id=%s | lead_id=%s",
                    request_id,
                    lead_id,
                )
                return Response(
                    {
                        "status": "error",
                        "message": "Invalid or expired review link",
                        "request_id": str(request_id),
                        "lead_id": str(lead_id),
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

        return Response(
            {
                "status": "success",
                "data": {
                    "id": str(review_request.id),
                    "request_name": review_request.request_name,
                    "description": review_request.description,
                    "collect_on": review_request.collect_on,
                    "lead_id": str(request_lead.lead_id) if request_lead else None,
                    "lead_name": request_lead.lead.full_name if request_lead else None,
                    "review_submitted": request_lead.review_submitted if request_lead else False,
                },
            },
            status=status.HTTP_200_OK,
        )

# REPUTATION MANAGEMENT - LIST REVIEWS FOR A REQUEST
# GET /api/reputation/review-request/<request_id>/reviews/
class ReviewListAPIView(APIView):
    def get(self, request, request_id):
        clinic = resolve_request_clinic(request, required=True)

        reviews = Review.objects.filter(
            review_request_id=request_id,
            review_request__clinic=clinic,
        )

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
    # ✅ No auth — leads are not registered users, they open the link from email
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        logger.info(
            "ReviewCreate received | body=%s | headers=Content-Type:%s",
            request.data,
            request.content_type,
        )

        payload = request.data if isinstance(request.data, dict) else {}
        request_id = (
            payload.get("review_request")
            or payload.get("request")
            or payload.get("request_id")
        )
        lead_id = payload.get("lead") or payload.get("lead_id")
        rating_value = payload.get("rating") or payload.get("stars") or payload.get("score")
        review_text = (
            payload.get("review_text")
            or payload.get("comment")
            or payload.get("feedback")
            or ""
        )

        if not request_id or not lead_id:
            error_message = "Review request and lead are required."
            logger.warning(
                "ReviewCreate missing identifiers | request_id=%s | lead_id=%s | body=%s",
                request_id,
                lead_id,
                payload,
            )
            return Response(
                {
                    "status": "error",
                    "error": error_message,
                    "errors": {
                        "review_request": ["This field is required."],
                        "lead": ["This field is required."],
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        request_lead = ReviewRequestLead.objects.select_related("review_request", "lead").filter(
            review_request_id=request_id,
            lead_id=lead_id,
        ).first()

        if not request_lead:
            logger.warning(
                "ReviewCreate invalid link | request_id=%s | lead_id=%s",
                request_id,
                lead_id,
            )
            return Response(
                {
                    "status": "error",
                    "error": "Invalid or expired review link.",
                    "errors": {
                        "review_request": ["No matching review request was found for this lead."],
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            rating = float(rating_value)
        except (TypeError, ValueError):
            logger.warning(
                "ReviewCreate invalid rating | request_id=%s | lead_id=%s | rating=%s",
                request_id,
                lead_id,
                rating_value,
            )
            return Response(
                {
                    "status": "error",
                    "error": "Rating must be a number between 1 and 5.",
                    "errors": {
                        "rating": ["Enter a valid number between 1 and 5."],
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if rating < 1 or rating > 5:
            logger.warning(
                "ReviewCreate out-of-range rating | request_id=%s | lead_id=%s | rating=%s",
                request_id,
                lead_id,
                rating,
            )
            return Response(
                {
                    "status": "error",
                    "error": "Rating must be between 1 and 5.",
                    "errors": {
                        "rating": ["Ensure this value is between 1 and 5."],
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        review_text = str(review_text).strip()

        existing_review = (
            Review.objects.filter(
                review_request=request_lead.review_request,
                lead=request_lead.lead,
            )
            .order_by("-submitted_at", "-id")
            .first()
        )

        if existing_review:
            existing_review.rating = rating
            existing_review.review_text = review_text
            existing_review.save(update_fields=["rating", "review_text"])
            review = existing_review
            response_status = status.HTTP_200_OK
            response_message = "Review updated successfully"
        else:
            review = Review.objects.create(
                review_request=request_lead.review_request,
                lead=request_lead.lead,
                rating=rating,
                review_text=review_text,
            )
            response_status = status.HTTP_201_CREATED
            response_message = "Review submitted successfully"

        if not request_lead.review_submitted:
            request_lead.review_submitted = True
            request_lead.save(update_fields=["review_submitted"])

        serializer = ReviewSerializer(review)

        return Response(
            {
                "status": "success",
                "message": response_message,
                "data": serializer.data,
            },
            status=response_status,
        )

# REPUTATION MANAGEMENT - DASHBOARD INSIGHTS
# GET /api/reputation/dashboard/
class ReputationDashboardAPIView(APIView):

    def get(self, request):
        clinic = resolve_request_clinic(request, required=True)

        from django.db.models import Avg
        from restapi.models.reputation import ReviewRequest, Review, ReviewRequestLead

        total_requests = ReviewRequest.objects.filter(clinic=clinic).count()
        total_sent_requests = ReviewRequestLead.objects.filter(
            request_sent=True,
            review_request__clinic=clinic,
        ).count()

        total_reviews = Review.objects.filter(review_request__clinic=clinic).count()

        avg_rating = Review.objects.filter(review_request__clinic=clinic).aggregate(
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