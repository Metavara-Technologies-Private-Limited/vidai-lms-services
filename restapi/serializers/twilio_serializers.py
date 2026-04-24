from rest_framework import serializers
from restapi.models.lead import Lead
from restapi.models import TwilioMessage, TwilioCall
import re

class SendSMSSerializer(serializers.Serializer):
    lead_uuid = serializers.UUIDField(required=True)
    to = serializers.CharField()
    message = serializers.CharField()

    def validate_lead_uuid(self, value):
        if not Lead.objects.filter(id=value).exists():
            raise serializers.ValidationError("Invalid Lead UUID")
        return value


class MakeCallSerializer(serializers.Serializer):
    lead_uuid = serializers.UUIDField(required=True)
    to = serializers.CharField()

    def validate_lead_uuid(self, value):
        if not Lead.objects.filter(id=value).exists():
            raise serializers.ValidationError("Invalid Lead UUID")
        return value

    def validate_to(self, value):
        value = value.strip()

        # ❌ Empty
        if not value:
            raise serializers.ValidationError("Phone number required")

        # ❌ Dummy numbers
        if value in ["0000000000", "1111111111", "1234567890"]:
            raise serializers.ValidationError("Invalid phone number")

        # ❌ All same digits
        if len(set(value)) == 1:
            raise serializers.ValidationError("Invalid phone number")

        # ✅ India mobile validation
        if not re.match(r"^[6-9]\d{9}$", value):
            raise serializers.ValidationError("Invalid phone number format")

        return value
    


from rest_framework import serializers
from restapi.models import TwilioMessage, TwilioCall


class TwilioMessageListSerializer(serializers.ModelSerializer):
    lead_uuid = serializers.UUIDField(source="lead.id", read_only=True)

    class Meta:
        model = TwilioMessage
        fields = [
            "id",
            "lead_uuid",
            "sid",
            "from_number",
            "to_number",
            "body",
            "status",
            "direction",
            "created_at",
        ]


class TwilioCallListSerializer(serializers.ModelSerializer):
    lead_uuid = serializers.UUIDField(source="lead.id", read_only=True)

    class Meta:
        model = TwilioCall
        fields = [
            "id",
            "lead_uuid",
            "sid",
            "from_number",
            "to_number",
            "status",
            "created_at",
        ]