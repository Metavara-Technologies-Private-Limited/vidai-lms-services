from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from restapi.models import (
    TemplateMail,
    TemplateSMS,
    TemplateWhatsApp,
    TemplateMailDocument,
    TemplateSMSDocument,
    TemplateWhatsAppDocument,
)

from restapi.services.template_service import (
    create_template,
    update_template,
)


# =====================================================
# TEMPLATE MAIL DOCUMENT SERIALIZER
# =====================================================
class TemplateMailDocumentSerializer(serializers.ModelSerializer):
    """
    Serializer for Email Template Documents.
    Used inside Read Serializer to return attached documents.
    """
    class Meta:
        model = TemplateMailDocument
        fields = "__all__"


# =====================================================
# TEMPLATE SMS DOCUMENT SERIALIZER
# =====================================================
class TemplateSMSDocumentSerializer(serializers.ModelSerializer):
    """
    Serializer for SMS Template Documents.
    """
    class Meta:
        model = TemplateSMSDocument
        fields = "__all__"


# =====================================================
# TEMPLATE WHATSAPP DOCUMENT SERIALIZER
# =====================================================
class TemplateWhatsAppDocumentSerializer(serializers.ModelSerializer):
    """
    Serializer for WhatsApp Template Documents.
    """
    class Meta:
        model = TemplateWhatsAppDocument
        fields = "__all__"


# =====================================================
# EMAIL TEMPLATE SERIALIZERS
# =====================================================

class TemplateMailReadSerializer(serializers.ModelSerializer):
    """
    Read serializer for Email Templates.

    Includes:
    - Template fields
    - Related documents (nested)
    """

    documents = TemplateMailDocumentSerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = TemplateMail
        fields = "__all__"


class TemplateMailSerializer(serializers.ModelSerializer):
    """
    Write serializer for Email Templates.

    Responsibilities:
    - Validate required fields
    - Prevent duplicate template names per clinic
    - Safe handling for both CREATE and UPDATE
    """

    class Meta:
        model = TemplateMail
        fields = "__all__"

    # -------------------------------------------------
    # FIELD LEVEL VALIDATIONS
    # -------------------------------------------------

    def validate_subject(self, value):
        """
        Subject must not be empty for Email templates.
        """
        if not value or not value.strip():
            raise ValidationError("Subject is required for Email template.")
        return value

    def validate_body(self, value):
        """
        Email body must not be empty.
        """
        if not value or not value.strip():
            raise ValidationError("Email body cannot be empty.")
        return value

    # -------------------------------------------------
    # OBJECT LEVEL VALIDATION
    # -------------------------------------------------

    def validate(self, data):
        """
        FIXED DUPLICATE VALIDATION LOGIC

        Problem Earlier:
        - During UPDATE, duplicate check was detecting itself.
        - If clinic or name not passed in update,
          it caused incorrect duplicate errors.

        Solution:
        - Use existing instance values if not provided.
        - Exclude current instance during update.
        """

        # Use new value if provided, otherwise use existing instance value
        clinic = data.get("clinic") or (self.instance.clinic if self.instance else None)
        name = data.get("name") or (self.instance.name if self.instance else None)

        # If required fields are missing, skip duplicate check
        if not clinic or not name:
            return data

        # Query existing templates with same name and clinic
        queryset = TemplateMail.objects.filter(
            clinic=clinic,
            name=name,
            is_deleted=False
        )

        # IMPORTANT FIX:
        # Exclude current instance during update
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)

        if queryset.exists():
            raise ValidationError(
                "Email template with this name already exists for this clinic."
            )

        return data

    # -------------------------------------------------
    # CREATE HANDLER
    # -------------------------------------------------

    def create(self, validated_data):
        """
        Delegate creation to service layer.
        Keeps business logic outside serializer.
        """
        return create_template("mail", validated_data)

    # -------------------------------------------------
    # UPDATE HANDLER
    # -------------------------------------------------

    def update(self, instance, validated_data):
        """
        Delegate update to service layer.
        """
        return update_template("mail", instance, validated_data)


# =====================================================
# SMS TEMPLATE SERIALIZERS
# =====================================================

class TemplateSMSReadSerializer(serializers.ModelSerializer):
    """
    Read serializer for SMS Templates.
    Includes related documents.
    """

    documents = TemplateSMSDocumentSerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = TemplateSMS
        fields = "__all__"


class TemplateSMSSerializer(serializers.ModelSerializer):
    """
    Write serializer for SMS Templates.

    Responsibilities:
    - Validate body
    - Prevent duplicate names per clinic
    """

    class Meta:
        model = TemplateSMS
        fields = "__all__"

    def validate_body(self, value):
        """
        SMS body must not be empty.
        """
        if not value or not value.strip():
            raise ValidationError("SMS body cannot be empty.")
        return value

    def validate(self, data):
        """
        Duplicate name prevention logic (UPDATE SAFE).
        """

        clinic = data.get("clinic") or (self.instance.clinic if self.instance else None)
        name = data.get("name") or (self.instance.name if self.instance else None)

        if not clinic or not name:
            return data

        queryset = TemplateSMS.objects.filter(
            clinic=clinic,
            name=name,
            is_deleted=False
        )

        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)

        if queryset.exists():
            raise ValidationError(
                "SMS template with this name already exists for this clinic."
            )

        return data

    def create(self, validated_data):
        return create_template("sms", validated_data)

    def update(self, instance, validated_data):
        return update_template("sms", instance, validated_data)


# =====================================================
# WHATSAPP TEMPLATE SERIALIZERS
# =====================================================

class TemplateWhatsAppReadSerializer(serializers.ModelSerializer):
    """
    Read serializer for WhatsApp Templates.
    """

    documents = TemplateWhatsAppDocumentSerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = TemplateWhatsApp
        fields = "__all__"


class TemplateWhatsAppSerializer(serializers.ModelSerializer):
    """
    Write serializer for WhatsApp Templates.
    """

    class Meta:
        model = TemplateWhatsApp
        fields = "__all__"

    def validate_body(self, value):
        """
        WhatsApp body must not be empty.
        """
        if not value or not value.strip():
            raise ValidationError("WhatsApp body cannot be empty.")
        return value

    def validate(self, data):
        """
        Duplicate name prevention logic (UPDATE SAFE).
        """

        clinic = data.get("clinic") or (self.instance.clinic if self.instance else None)
        name = data.get("name") or (self.instance.name if self.instance else None)

        if not clinic or not name:
            return data

        queryset = TemplateWhatsApp.objects.filter(
            clinic=clinic,
            name=name,
            is_deleted=False
        )

        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)

        if queryset.exists():
            raise ValidationError(
                "WhatsApp template with this name already exists for this clinic."
            )

        return data

    def create(self, validated_data):
        return create_template("whatsapp", validated_data)

    def update(self, instance, validated_data):
        return update_template("whatsapp", instance, validated_data)
