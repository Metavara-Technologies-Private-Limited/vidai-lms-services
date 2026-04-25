from rest_framework import serializers
from restapi.models.lead import Lead
from restapi.models import TwilioMessage, TwilioCall


# =====================================================
# COMMON PHONE VALIDATOR FUNCTION
# =====================================================
def normalize_indian_number(value):
    value = value.strip()

    if not value:
        raise serializers.ValidationError("Phone number required")

    # Remove all non-digits
    value = "".join(ch for ch in value if ch.isdigit())

    # Normalize prefixes
    if value.startswith("91") and len(value) == 12:
        value = value[2:]
    elif value.startswith("0") and len(value) == 11:
        value = value[1:]

    # Length check
    if len(value) != 10:
        raise serializers.ValidationError("Phone number must be 10 digits")

    # Start digit check
    if value[0] not in ["6", "7", "8", "9"]:
        raise serializers.ValidationError("Invalid Indian mobile number")

    # Dummy numbers
    if value in ["0000000000", "1111111111", "1234567890"]:
        raise serializers.ValidationError("Invalid phone number")

    # All same digits
    if len(set(value)) == 1:
        raise serializers.ValidationError("Invalid phone number")

    return value


# =====================================================
# SEND SMS SERIALIZER
# =====================================================
class SendSMSSerializer(serializers.Serializer):
    lead_uuid = serializers.UUIDField(required=True)
    to = serializers.CharField()
    message = serializers.CharField()

    def validate_lead_uuid(self, value):
        if not Lead.objects.filter(id=value).exists():  # ⚠️ change to uuid if needed
            raise serializers.ValidationError("Invalid Lead UUID")
        return value

    def validate_to(self, value):
        return normalize_indian_number(value)


# =====================================================
# MAKE CALL SERIALIZER
# =====================================================
class MakeCallSerializer(serializers.Serializer):
    lead_uuid = serializers.UUIDField(required=True)
    to = serializers.CharField()

    def validate_lead_uuid(self, value):
        if not Lead.objects.filter(id=value).exists():  # ⚠️ change to uuid if needed
            raise serializers.ValidationError("Invalid Lead UUID")
        return value

    def validate_to(self, value):
        return normalize_indian_number(value)


# =====================================================
# TWILIO MESSAGE LIST SERIALIZER
# =====================================================
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


# =====================================================
# TWILIO CALL LIST SERIALIZER
# =====================================================
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