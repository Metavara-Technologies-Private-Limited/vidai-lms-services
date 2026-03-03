from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from restapi.models import (
    Campaign,
    CampaignSocialMediaConfig,
    CampaignEmailConfig,
)

from restapi.services.campaign_service import create_campaign, update_campaign


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
            "post_id",        # ✅ Added
            "is_active",
        ]
        read_only_fields = ["post_id"]   # ✅ Backend controlled


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


# =====================================================
# Social Media Campaign Serializer (Flexible Version)
# =====================================================
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

    # ✅ Flexible Content
    campaign_content = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        default=""
    )

    schedule_date_range = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        default=""
    )

    enter_time = serializers.TimeField()

    # ✅ JSON Support
    platform_data = serializers.JSONField(
        required=False,
        default=dict
    )

    budget_data = serializers.JSONField(
        required=False,
        default=dict
    )

    # ✅ Status Controls
    status = serializers.CharField(
        required=False,
        allow_blank=True,
        default="draft"
    )

    is_active = serializers.BooleanField(
        required=False,
        default=False
    )


# =====================================================
# Email Campaign CREATE Serializer
# =====================================================
class EmailCampaignCreateSerializer(serializers.Serializer):
    clinic = serializers.IntegerField()
    campaign_name = serializers.CharField()
    campaign_description = serializers.CharField()
    campaign_objective = serializers.CharField()
    target_audience = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    selected_start = serializers.DateField()
    selected_end = serializers.DateField()
    enter_time = serializers.TimeField()

    email = CampaignEmailSerializer(many=True)


# =====================================================
# Campaign WRITE Serializer
# =====================================================
class CampaignSerializer(serializers.ModelSerializer):

    social_media = CampaignSocialMediaSerializer(many=True, required=False)
    email = CampaignEmailSerializer(many=True, required=False)

    # ✅ JSONB Fields
    platform_data = serializers.JSONField(required=False)
    budget_data = serializers.JSONField(required=False)

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
            "status",
            "is_active",
            "platform_data",
            "budget_data",
            "social_media",
            "email",
        ]

    # =====================================================
    # VALIDATION
    # =====================================================
    def validate(self, data):

        if data["start_date"] > data["end_date"]:
            raise ValidationError("Start date cannot be after end date")

        # ✅ platform_data validation
        platform_data = data.get("platform_data")
        if platform_data and not isinstance(platform_data, dict):
            raise ValidationError({
                "platform_data": "Must be a valid JSON object"
            })

        # ✅ budget_data validation
        budget_data = data.get("budget_data")
        if budget_data:
            if not isinstance(budget_data, dict):
                raise ValidationError({
                    "budget_data": "Must be a valid JSON object"
                })

            if "total_budget" in budget_data:
                if float(budget_data["total_budget"]) < 0:
                    raise ValidationError({
                        "budget_data": "Total budget cannot be negative"
                    })

        return data

    # =====================================================
    # CREATE & UPDATE
    # =====================================================
    def create(self, validated_data):
        return create_campaign(validated_data)

    def update(self, instance, validated_data):
        return update_campaign(instance, validated_data)