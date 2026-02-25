# =====================================================
# TEMPLATE SERVICE
# =====================================================

from django.db import transaction
from rest_framework.exceptions import ValidationError

from restapi.models import (
    TemplateMail,
    TemplateSMS,
    TemplateWhatsApp,
    TemplateMailDocument,
    TemplateSMSDocument,
    TemplateWhatsAppDocument,
)


@transaction.atomic
def create_template(template_type, validated_data):

    # ✅ NEW: Extract documents from request
    documents_data = validated_data.pop("documents", [])

    if template_type == "mail":
        template = TemplateMail.objects.create(**validated_data)
        document_model = TemplateMailDocument

    elif template_type == "sms":
        template = TemplateSMS.objects.create(**validated_data)
        document_model = TemplateSMSDocument

    elif template_type == "whatsapp":
        template = TemplateWhatsApp.objects.create(**validated_data)
        document_model = TemplateWhatsAppDocument

    else:
        raise ValidationError("Invalid template type.")

    # ✅ NEW: Save related documents
    for doc in documents_data:
        document_model.objects.create(
            template=template,
            file=doc.get("file")
        )

    return template


@transaction.atomic
def update_template(template_type, instance, validated_data):

    # ✅ NEW: Extract documents if present
    documents_data = validated_data.pop("documents", [])

    # Update main fields
    for field, value in validated_data.items():
        setattr(instance, field, value)

    instance.save()

    # ✅ NEW: Determine correct document model
    if template_type == "mail":
        document_model = TemplateMailDocument
    elif template_type == "sms":
        document_model = TemplateSMSDocument
    elif template_type == "whatsapp":
        document_model = TemplateWhatsAppDocument
    else:
        raise ValidationError("Invalid template type.")

    # ✅ NEW: Update existing documents safely
    existing_documents = {
        str(doc.id): doc
        for doc in instance.documents.all()
    }

    for doc in documents_data:

        doc_id = str(doc.get("id"))

        if not doc_id:
            raise ValidationError("Document id is required for update.")

        if doc_id not in existing_documents:
            raise ValidationError("Invalid document id.")

        document_instance = existing_documents[doc_id]

        if "file" in doc:
            document_instance.file = doc["file"]
            document_instance.save()

    instance.refresh_from_db()

    return instance