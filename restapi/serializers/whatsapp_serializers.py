# ─────────────────────────────────────────────────────────────────────────────
# APPEND THESE to your existing serializers.py
# Original SendSMSSerializer / MakeCallSerializer etc. are NOT touched
# ─────────────────────────────────────────────────────────────────────────────

from rest_framework import serializers
from restapi.models import WhatsAppTemplate, WhatsAppMessage


# =====================================================
# WHATSAPP TEMPLATE SERIALIZERS
# =====================================================

class WhatsAppTemplateCreateSerializer(serializers.Serializer):
    """Validates payload for creating + submitting a template to Meta."""

    name = serializers.CharField(
        max_length=255,
        help_text="Lowercase, underscores only e.g. appointment_reminder",
    )
    category = serializers.ChoiceField(
        choices=["MARKETING", "UTILITY", "AUTHENTICATION"],
    )
    language = serializers.CharField(
        max_length=20,
        default="en",
        help_text="BCP-47 code e.g. en, en_US, hi",
    )
    body_text = serializers.CharField(
        help_text="Message body. Use {{1}}, {{2}} for variables.",
    )
    variables = serializers.ListField(
        child=serializers.CharField(),
        default=list,
        help_text="Example values for each placeholder e.g. ['John', '10 AM']",
    )
    header_text = serializers.CharField(
        max_length=60,
        required=False,
        allow_blank=True,
        default="",
    )
    footer_text = serializers.CharField(
        max_length=60,
        required=False,
        allow_blank=True,
        default="",
    )

    def validate_name(self, value):
        import re
        if not re.match(r"^[a-z0-9_]+$", value):
            raise serializers.ValidationError(
                "Template name must be lowercase letters, digits, and underscores only."
            )
        return value

    def validate(self, data):
        import re
        body       = data.get("body_text", "")
        variables  = data.get("variables", [])
        # Count placeholders like {{1}}, {{2}} in body
        placeholders = re.findall(r"\{\{\d+\}\}", body)
        if len(placeholders) != len(variables):
            raise serializers.ValidationError(
                f"body_text has {len(placeholders)} placeholder(s) but "
                f"{len(variables)} variable example(s) were provided. They must match."
            )
        return data


class WhatsAppTemplateListSerializer(serializers.ModelSerializer):
    """Read serializer for listing templates."""

    class Meta:
        model  = WhatsAppTemplate
        fields = [
            "id",
            "meta_template_id",
            "name",
            "category",
            "language",
            "header_text",
            "body_text",
            "footer_text",
            "variables",
            "status",
            "created_at",
            "updated_at",
        ]


# =====================================================
# WHATSAPP SEND SERIALIZERS
# =====================================================

class WhatsAppSendSerializer(serializers.Serializer):
    """Validates payload for sending a single WhatsApp message."""

    lead_uuid       = serializers.UUIDField(required=False, allow_null=True)
    to_number       = serializers.CharField()
    template_name   = serializers.CharField()
    language        = serializers.CharField(default="en")
    variable_values = serializers.ListField(
        child=serializers.CharField(allow_blank=True),
        default=list,
    )

    def validate_to_number(self, value):
        """Accept E.164 or Indian 10-digit numbers."""
        from restapi.serializers.twilio_serializers import normalize_indian_number
        return normalize_indian_number(value)

    def validate_template_name(self, value):
        template = WhatsAppTemplate.objects.filter(
            name=value,
            status="APPROVED",
        ).first()
        if not template:
            raise serializers.ValidationError(
                f"Template '{value}' does not exist or is not yet approved by Meta."
            )
        return value

    def validate(self, data):
        import re
        template_name = data.get("template_name")
        variables     = data.get("variable_values", [])
        template      = WhatsAppTemplate.objects.filter(name=template_name).first()

        if template:
            placeholders = re.findall(r"\{\{\d+\}\}", template.body_text)
            if len(placeholders) != len(variables):
                raise serializers.ValidationError(
                    f"Template '{template_name}' needs {len(placeholders)} variable(s) "
                    f"but {len(variables)} were provided."
                )
        return data


class WhatsAppBulkSendSerializer(serializers.Serializer):
    """Validates payload for bulk sending a template to multiple recipients."""

    template_name = serializers.CharField()
    language      = serializers.CharField(default="en")
    recipients    = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        help_text=(
            "List of {lead_uuid, to_number, variable_values} dicts. "
            "lead_uuid is optional."
        ),
    )

    def validate_template_name(self, value):
        template = WhatsAppTemplate.objects.filter(
            name=value,
            status="APPROVED",
        ).first()
        if not template:
            raise serializers.ValidationError(
                f"Template '{value}' does not exist or is not yet approved."
            )
        return value

    def validate_recipients(self, value):
        from restapi.serializers.twilio_serializers import normalize_indian_number
        errors = []
        for i, r in enumerate(value):
            if "to_number" not in r:
                errors.append(f"recipients[{i}]: 'to_number' is required.")
                continue
            try:
                value[i]["to_number"] = normalize_indian_number(r["to_number"])
            except Exception as e:
                errors.append(f"recipients[{i}].to_number: {e}")
        if errors:
            raise serializers.ValidationError(errors)
        return value


# =====================================================
# WHATSAPP MESSAGE LIST SERIALIZER
# =====================================================

class WhatsAppMessageListSerializer(serializers.ModelSerializer):
    """Read serializer for listing sent WhatsApp messages."""

    lead_uuid   = serializers.UUIDField(source="lead.id",   read_only=True)
    clinic_id   = serializers.IntegerField(source="clinic.id", read_only=True)
    template_id = serializers.IntegerField(source="template.id", read_only=True)

    class Meta:
        model  = WhatsAppMessage
        fields = [
            "id",
            "lead_uuid",
            "clinic_id",
            "template_id",
            "sid",
            "from_number",
            "to_number",
            "template_name",
            "language",
            "variable_values",
            "status",
            "created_at",
        ]