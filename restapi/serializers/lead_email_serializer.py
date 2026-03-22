from rest_framework import serializers
from restapi.models import LeadEmail



class LeadEmailSerializer(serializers.ModelSerializer):

    send_now = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = LeadEmail
        fields = (
            "id",
            "lead",
            "subject",
            "email_body",
            "sender_email",
            "scheduled_at",
            "status",
            "sent_at",
            "failed_reason",
            "created_at",
            "send_now",
        )
        read_only_fields = (
            "id",
            "status",
            "sent_at",
            "failed_reason",
            "created_at",
        )

    def create(self, validated_data):
        # Remove non-model field before saving
        validated_data.pop("send_now", None)
        return super().create(validated_data)
    
class LeadMailListSerializer(serializers.ModelSerializer):
    lead_uuid = serializers.UUIDField(source="lead.id", read_only=True)

    class Meta:
        model = LeadEmail
        fields = [
            "id",
            "lead_uuid",
            "subject",
            "sender_email",
            "email_body",
            "status",
            "scheduled_at",
            "sent_at",
            "created_at",
        ]