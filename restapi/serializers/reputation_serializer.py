from rest_framework import serializers
from restapi.models.reputation import ReviewRequest, ReviewRequestLead, Review


# =====================================================
# REVIEW REQUEST SERIALIZER
# =====================================================

class ReviewRequestSerializer(serializers.ModelSerializer):

    lead_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = ReviewRequest
        fields = [
            "id",
            "clinic",
            "request_name",
            "description",
            "collect_on",
            "mode",
            "subject",
            "message",
            "schedule_date",
            "schedule_time",
            "status",
            "created_at",
            "lead_ids",
        ]

        read_only_fields = [
            "id",
            "created_at",
        ]

    def create(self, validated_data):
        # ✅ correct import (based on your folder)
        from restapi.services.reputation_service import create_review_request
        return create_review_request(validated_data)


# =====================================================
# REVIEW REQUEST LEAD SERIALIZER
# =====================================================

class ReviewRequestLeadSerializer(serializers.ModelSerializer):

    class Meta:
        model = ReviewRequestLead
        fields = [
            "id",
            "review_request",
            "lead",
            "request_sent",
            "review_submitted",
        ]

        read_only_fields = [
            "id",
        ]


# =====================================================
# REVIEW SERIALIZER
# =====================================================

class ReviewSerializer(serializers.ModelSerializer):

    lead_name = serializers.CharField(
        source="lead.full_name",
        read_only=True
    )

    class Meta:
        model = Review
        fields = [
            "id",
            "review_request",
            "lead",
            "lead_name",
            "rating",
            "review_text",
            "submitted_at",
        ]

        read_only_fields = [
            "id",
            "lead_name",
            "submitted_at",
        ]