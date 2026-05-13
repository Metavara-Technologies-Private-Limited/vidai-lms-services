from rest_framework import serializers
from restapi.models import CampaignSocialPost

class CampaignSocialPostCallbackSerializer(serializers.Serializer):
    """
    Handles Zapier callbacks for LinkedIn campaign creation
    + social post callbacks.
    """

    # existing
    campaign_id = serializers.CharField(required=False)
    platform = serializers.CharField()
    status = serializers.CharField()

    post_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True
    )

    post_urn = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True
    )

    error_message = serializers.CharField(
        required=False,
        allow_blank=True
    )

    # ------------------------------------
    # NEW FOR LINKEDIN CREATE ACK
    # ------------------------------------

    internal_campaign_uuid = serializers.CharField(
        required=False
    )

    campaign_urn = serializers.CharField(
        required=False,
        allow_blank=True
    )

    creative_urn = serializers.CharField(
        required=False,
        allow_blank=True
    )

    account_id = serializers.CharField(
        required=False,
        allow_blank=True
    )

    campaign_group_urn = serializers.CharField(
        required=False,
        allow_blank=True
    )

    ads_manager_url = serializers.CharField(
        required=False,
        allow_blank=True
    )

class CampaignSocialPostReadSerializer(serializers.ModelSerializer):

    image = serializers.SerializerMethodField()

    class Meta:
        model = CampaignSocialPost

        fields = [
            "id",
            "campaign",
            "platform_name",
            "post_id",
            "status",
            "error_message",
            "requested_at",
            "synced_at",
            "creative_id",
            "ads_manager_url",

            # image fields
            "uploaded_image",
            "image_url",
            "image",

            "document_name",
            "created_at",
            "updated_at",
        ]

    def get_image(self, obj):

        # ==========================================
        # PRIORITY 1 → IMAGE URL
        # ==========================================
        if obj.image_url:
            return obj.image_url

        # ==========================================
        # PRIORITY 2 → UPLOADED IMAGE
        # ==========================================
        if obj.uploaded_image:

            request = self.context.get("request")

            if request:
                return request.build_absolute_uri(
                    obj.uploaded_image.url
                )

            return obj.uploaded_image.url

        return None