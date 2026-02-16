from rest_framework import serializers

from restapi.models import CampaignSocialPost

class CampaignSocialPostCallbackSerializer(serializers.Serializer):
    """
    Used by Zapier callback to update post status
    """

    campaign_id = serializers.UUIDField()
    platform = serializers.ChoiceField(
        choices=[
            CampaignSocialPost.FACEBOOK,
            CampaignSocialPost.LINKEDIN,
        ]
    )
    post_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True
    )
    status = serializers.ChoiceField(
        choices=[
            CampaignSocialPost.POSTED,
            CampaignSocialPost.FAILED,
        ]
    )
    error_message = serializers.CharField(
        required=False,
        allow_blank=True
    )


class CampaignSocialPostReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignSocialPost
        fields = "__all__"
