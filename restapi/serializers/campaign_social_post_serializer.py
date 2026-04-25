from rest_framework import serializers


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