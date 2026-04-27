from rest_framework import serializers
from restapi.models import LeadEmail


class LeadEmailSerializer(serializers.ModelSerializer):

    send_now = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = LeadEmail
        fields = (
            "id",
            "lead",
            "clinic",
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
            "clinic",   # ✅ auto handled
            "status",
            "sent_at",
            "failed_reason",
            "created_at",
        )

    def create(self, validated_data):
        # remove send_now (handled in view)
        validated_data.pop("send_now", None)

        lead = validated_data.get("lead")

        # ✅ AUTO ASSIGN CLINIC FROM LEAD
        if lead:
            validated_data["clinic"] = getattr(lead, "clinic", None)

        return super().create(validated_data)


# =====================================================
# LIST SERIALIZER
# =====================================================
class LeadMailListSerializer(serializers.ModelSerializer):
    lead_uuid = serializers.UUIDField(source="lead.id", read_only=True)
    clinic_id = serializers.IntegerField(source="clinic.id", read_only=True)

    class Meta:
        model = LeadEmail
        fields = [
            "id",
            "lead_uuid",
            "clinic_id",
            "subject",
            "sender_email",
            "email_body",
            "status",
            "scheduled_at",
            "sent_at",
            "created_at",
        ]