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

    total_leads = serializers.SerializerMethodField()
    requests_sent = serializers.SerializerMethodField()
    reviews_submitted = serializers.SerializerMethodField()
    avg_rating = serializers.SerializerMethodField()
    conversion_rate = serializers.SerializerMethodField()

    def _get_prefetched_items(self, obj, attr_name):
        prefetched_cache = getattr(obj, "_prefetched_objects_cache", {})
        if attr_name in prefetched_cache:
            return prefetched_cache[attr_name]
        return None

    def _get_request_leads(self, obj):
        prefetched_leads = self._get_prefetched_items(obj, "leads")
        if prefetched_leads is not None:
            return prefetched_leads
        return list(obj.leads.all())

    def _get_reviews(self, obj):
        prefetched_reviews = self._get_prefetched_items(obj, "reviews")
        if prefetched_reviews is not None:
            return prefetched_reviews
        return list(obj.reviews.all())

    def get_total_leads(self, obj):
        return len(self._get_request_leads(obj))

    def get_requests_sent(self, obj):
        return sum(1 for request_lead in self._get_request_leads(obj) if request_lead.request_sent)

    def get_reviews_submitted(self, obj):
        return len(self._get_reviews(obj))

    def get_avg_rating(self, obj):
        reviews = self._get_reviews(obj)
        if not reviews:
            return 0.0

        average = sum(float(review.rating) for review in reviews) / len(reviews)
        return round(average, 1)

    def get_conversion_rate(self, obj):
        requests_sent = self.get_requests_sent(obj)
        if requests_sent == 0:
            return 0.0

        reviews_submitted = self.get_reviews_submitted(obj)
        return round((reviews_submitted / requests_sent) * 100, 1)

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
            "total_leads",
            "requests_sent",
            "reviews_submitted",
            "avg_rating",
            "conversion_rate",
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
            "sent_link",
        ]

        read_only_fields = [
            "id",
            "sent_link",
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