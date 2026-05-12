# ─────────────────────────────────────────────────────────────────────────────
# APPEND THESE to your existing serializers file
# Original serializers are NOT touched
#
# FIX: Uses your existing TemplateWhatsApp model (restapi_template_whatsapp)
#      instead of the removed WhatsAppTemplate model.
# ─────────────────────────────────────────────────────────────────────────────

import re

from rest_framework         import serializers
from restapi.models.template_whatsapp import TemplateWhatsApp
from restapi.models          import WhatsAppMessage     # ← only new model


# =====================================================
# WHATSAPP SEND SERIALIZERS
# =====================================================

class WhatsAppSendSerializer(serializers.Serializer):
    """Validates payload for sending a single WhatsApp message."""

    lead_uuid       = serializers.UUIDField(required=False, allow_null=True)
    to_number       = serializers.CharField()
    template_id     = serializers.UUIDField(
        help_text="UUID of the TemplateWhatsApp record from your DB",
    )
    variable_values = serializers.ListField(
        child=serializers.CharField(allow_blank=True),
        default=list,
        help_text="Values to substitute into the template body, in order",
    )

    def validate_to_number(self, value):
        """Accept E.164 or Indian 10-digit numbers."""
        from restapi.serializers.twilio_serializers import normalize_indian_number
        return normalize_indian_number(value)

    def validate_template_id(self, value):
        """Ensure the TemplateWhatsApp exists, is active, and not deleted."""
        template = TemplateWhatsApp.objects.filter(
            id=value,
            is_active=True,
            is_deleted=False,
        ).first()
        if not template:
            raise serializers.ValidationError(
                f"Template with id '{value}' does not exist or is inactive."
            )
        return value

    def validate(self, data):
        """Ensure the number of variable_values matches placeholders in body."""
        template_id = data.get("template_id")
        variables   = data.get("variable_values", [])

        if template_id:
            template = TemplateWhatsApp.objects.filter(id=template_id).first()
            if template:
                placeholders = re.findall(r"\{\{\d+\}\}", template.body)
                if len(placeholders) != len(variables):
                    raise serializers.ValidationError(
                        f"Template body has {len(placeholders)} placeholder(s) "
                        f"but {len(variables)} variable value(s) were provided."
                    )
        return data


class WhatsAppBulkSendSerializer(serializers.Serializer):
    """Validates payload for bulk sending a template to multiple recipients."""

    template_id = serializers.UUIDField(
        help_text="UUID of the TemplateWhatsApp record from your DB",
    )
    recipients  = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        help_text=(
            "List of {lead_uuid (optional), to_number, variable_values} dicts."
        ),
    )

    def validate_template_id(self, value):
        template = TemplateWhatsApp.objects.filter(
            id=value,
            is_active=True,
            is_deleted=False,
        ).first()
        if not template:
            raise serializers.ValidationError(
                f"Template with id '{value}' does not exist or is inactive."
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
            except Exception as exc:
                errors.append(f"recipients[{i}].to_number: {exc}")
        if errors:
            raise serializers.ValidationError(errors)
        return value


# =====================================================
# WHATSAPP MESSAGE LIST SERIALIZER
# =====================================================

class WhatsAppMessageListSerializer(serializers.ModelSerializer):
    """Read serializer for listing sent WhatsApp messages."""

    lead_uuid   = serializers.UUIDField(source="lead.id",      read_only=True)
    clinic_id   = serializers.IntegerField(source="clinic.id", read_only=True)
    template_id = serializers.UUIDField(source="template.id",  read_only=True)

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