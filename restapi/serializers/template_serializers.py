# =====================================================
# SERIALIZERS
# =====================================================

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
# DOCUMENT SERIALIZERS
# =====================================================

class TemplateMailDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateMailDocument
        fields = "__all__"


class TemplateSMSDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateSMSDocument
        fields = "__all__"


class TemplateWhatsAppDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateWhatsAppDocument
        fields = "__all__"


# =====================================================
# EMAIL TEMPLATE SERIALIZERS
# =====================================================

class TemplateMailReadSerializer(serializers.ModelSerializer):

    documents = TemplateMailDocumentSerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = TemplateMail
        fields = "__all__"


class TemplateMailSerializer(serializers.ModelSerializer):

    # ✅ NEW: Allow documents during CREATE/UPDATE
    documents = TemplateMailDocumentSerializer(
        many=True,
        required=False
    )

    class Meta:
        model = TemplateMail
        fields = "__all__"

    def validate_subject(self, value):
        if not value or not value.strip():
            raise ValidationError("Subject is required for Email template.")
        return value

    def validate_body(self, value):
        if not value or not value.strip():
            raise ValidationError("Email body cannot be empty.")
        return value

    def validate(self, data):

        clinic = data.get("clinic") or (self.instance.clinic if self.instance else None)
        name = data.get("name") or (self.instance.name if self.instance else None)

        if not clinic or not name:
            return data

        queryset = TemplateMail.objects.filter(
            clinic=clinic,
            name=name,
            is_deleted=False
        )

        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)

        if queryset.exists():
            raise ValidationError(
                "Email template with this name already exists for this clinic."
            )

        return data

    def create(self, validated_data):
        return create_template("mail", validated_data)

    def update(self, instance, validated_data):
        return update_template("mail", instance, validated_data)


# =====================================================
# SMS TEMPLATE SERIALIZERS
# =====================================================

class TemplateSMSReadSerializer(serializers.ModelSerializer):

    documents = TemplateSMSDocumentSerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = TemplateSMS
        fields = "__all__"


class TemplateSMSSerializer(serializers.ModelSerializer):

    # ✅ NEW: Allow documents during CREATE/UPDATE
    documents = TemplateSMSDocumentSerializer(
        many=True,
        required=False
    )

    class Meta:
        model = TemplateSMS
        fields = "__all__"

    def validate_body(self, value):
        if not value or not value.strip():
            raise ValidationError("SMS body cannot be empty.")
        return value

    def validate(self, data):

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

    documents = TemplateWhatsAppDocumentSerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = TemplateWhatsApp
        fields = "__all__"


class TemplateWhatsAppSerializer(serializers.ModelSerializer):

    # ✅ NEW: Allow documents during CREATE/UPDATE
    documents = TemplateWhatsAppDocumentSerializer(
        many=True,
        required=False
    )

    class Meta:
        model = TemplateWhatsApp
        fields = "__all__"

    def validate_body(self, value):
        if not value or not value.strip():
            raise ValidationError("WhatsApp body cannot be empty.")
        return value

    def validate(self, data):

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