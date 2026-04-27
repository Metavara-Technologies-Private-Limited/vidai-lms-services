from rest_framework import serializers
from restapi.models.lead import Lead
from restapi.models import TwilioMessage, TwilioCall


# =====================================================
# COMMON PHONE VALIDATOR FUNCTION (YOUR LOGIC)
# =====================================================
def normalize_indian_number(value):
    value = value.strip()

    if not value:
        raise serializers.ValidationError("Phone number required")

    # -----------------------------
    # CASE 1: International number
    # -----------------------------
    if value.startswith("+"):
        digits = value[1:]

        if not digits.isdigit():
            raise serializers.ValidationError("Invalid international phone number")

        # E.164 standard: 7 to 15 digits
        if not (7 <= len(digits) <= 15):
            raise serializers.ValidationError("Invalid international phone number")

        return value  # ✅ Keep as is

    # -----------------------------
    # CASE 2: Indian number (NO +)
    # -----------------------------
    value = "".join(ch for ch in value if ch.isdigit())

    # Remove prefixes
    if value.startswith("91") and len(value) == 12:
        value = value[2:]
    elif value.startswith("0") and len(value) == 11:
        value = value[1:]

    # Validate Indian number
    if len(value) != 10:
        raise serializers.ValidationError("Phone number must be 10 digits")

    if value[0] not in ["6", "7", "8", "9"]:
        raise serializers.ValidationError("Invalid Indian mobile number")

    if value in ["0000000000", "1111111111", "1234567890"]:
        raise serializers.ValidationError("Invalid phone number")

    if len(set(value)) == 1:
        raise serializers.ValidationError("Invalid phone number")

    # ✅ Auto assign +91
    return f"+91{value}"


# =====================================================
# SEND SMS SERIALIZER
# =====================================================
class SendSMSSerializer(serializers.Serializer):
    lead_uuid = serializers.UUIDField(required=True)
    to = serializers.CharField()
    message = serializers.CharField()

    def validate_lead_uuid(self, value):
        if not Lead.objects.filter(id=value).exists():
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
        if not Lead.objects.filter(id=value).exists():
            raise serializers.ValidationError("Invalid Lead UUID")
        return value

    def validate_to(self, value):
        return normalize_indian_number(value)


# =====================================================
# TWILIO MESSAGE LIST SERIALIZER
# =====================================================
class TwilioMessageListSerializer(serializers.ModelSerializer):
    lead_uuid = serializers.UUIDField(source="lead.id", read_only=True)
    clinic_id = serializers.IntegerField(source="clinic.id", read_only=True)

    class Meta:
        model = TwilioMessage
        fields = [
            "id",
            "lead_uuid",
            "clinic_id",
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
    clinic_id = serializers.IntegerField(source="clinic.id", read_only=True)

    class Meta:
        model = TwilioCall
        fields = [
            "id",
            "lead_uuid",
            "clinic_id",
            "sid",
            "from_number",
            "to_number",
            "status",
            "created_at",
        ]