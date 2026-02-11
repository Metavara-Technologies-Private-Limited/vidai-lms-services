from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from restapi.models import (
    Campaign,
    CampaignSocialMediaConfig,
    CampaignEmailConfig,
)

from restapi.services.campaign_service import (
    create_campaign,
)


# =====================================================
# Social Media Config Serializer
# =====================================================
class CampaignSocialMediaSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = CampaignSocialMediaConfig
        fields = [
            "id",
            "platform_name",
            "is_active",
        ]


# =====================================================
# Email Config Serializer
# =====================================================
class CampaignEmailSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = CampaignEmailConfig
        fields = [
            "id",
            "audience_name",
            "subject",
            "email_body",
            "template_name",
            "sender_email",
            "scheduled_at",
            "is_active",
        ]


# =====================================================
# Campaign READ Serializer
# =====================================================
class CampaignReadSerializer(serializers.ModelSerializer):
    social_media = CampaignSocialMediaSerializer(
        source="social_configs",
        many=True
    )
    email = CampaignEmailSerializer(
        source="email_configs",
        many=True
    )

    class Meta:
        model = Campaign
        fields = "__all__"

class SocialMediaCampaignSerializer(serializers.Serializer):
    clinic = serializers.IntegerField()
    campaign_name = serializers.CharField()
    campaign_description = serializers.CharField()
    campaign_objective = serializers.CharField()
    target_audience = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    select_ad_accounts = serializers.ListField(
        child=serializers.CharField()
    )
    campaign_mode = serializers.ListField(
        child=serializers.CharField()
    )
    campaign_content = serializers.CharField()
    schedule_date_range = serializers.CharField()
    enter_time = serializers.TimeField()

# =====================================================
# Campaign WRITE Serializer
# =====================================================
class CampaignSerializer(serializers.ModelSerializer):
    social_media = CampaignSocialMediaSerializer(
        many=True,
        required=False
    )
    email = CampaignEmailSerializer(
        many=True,
        required=False
    )

    class Meta:
        model = Campaign
        fields = [
            "id",
            "clinic",
            "campaign_name",
            "campaign_description",
            "campaign_objective",
            "target_audience",
            "start_date",
            "end_date",
            "adv_accounts",
            "campaign_mode",
            "campaign_content",
            "selected_start",
            "selected_end",
            "enter_time",
            "is_active",
            "social_media",
            "email",
            "social_media",
            "email",
        ]

    # =========================
    # CREATE
    # =========================
    def create(self, validated_data):
        return create_campaign(validated_data)
    
    # =========================
    # UPDATE
    # =========================
    def update(self, instance, validated_data):
        from restapi.services.campaign_service import update_campaign
        return update_campaign(instance, validated_data)

