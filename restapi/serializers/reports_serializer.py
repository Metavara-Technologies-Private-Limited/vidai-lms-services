from rest_framework import serializers
from restapi.models.reports import CallLog, CampaignMetrics


class CallLogSerializer(serializers.ModelSerializer):
    lead_name = serializers.CharField(source="lead.full_name", read_only=True)
    received_by_name = serializers.CharField(source="received_by.username", read_only=True)

    class Meta:
        model = CallLog
        fields = "__all__"


class CampaignMetricsSerializer(serializers.ModelSerializer):
    campaign_name = serializers.CharField(source="campaign.campaign_name", read_only=True)
    clinic_id = serializers.UUIDField(source="campaign.clinic.id", read_only=True)

    class Meta:
        model = CampaignMetrics
        fields = "__all__"