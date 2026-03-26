from django.core.mail import send_mail
from django.utils import timezone
from django.utils.html import strip_tags
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from restapi.models import (
    Lead,
    Clinic,
    Department,
    Campaign,
    LeadDocument,
    LeadEmail,
)


# =====================================================
# CREATE LEAD
# =====================================================
@transaction.atomic
def create_lead(validated_data):

    documents = validated_data.pop("documents", [])

    try:
        clinic = Clinic.objects.get(id=validated_data.pop("clinic_id"))
    except Clinic.DoesNotExist:
        raise ValidationError({"clinic_id": "Invalid clinic_id"})

    try:
        department = Department.objects.get(
            id=validated_data.pop("department_id"),
            clinic=clinic
        )
    except Department.DoesNotExist:
        raise ValidationError({"department_id": "Invalid department_id"})

    campaign = None
    campaign_id = validated_data.pop("campaign_id", None)
    if campaign_id:
        campaign = Campaign.objects.filter(id=campaign_id).first()

    # ✅ NEW (NO FK)
    assigned_to_id = validated_data.pop("assigned_to_id", None)
    assigned_to_name = validated_data.pop("assigned_to_name", None)

    personal_id = validated_data.pop("personal_id", None)
    personal_name = validated_data.pop("personal_name", None)

    created_by_id = validated_data.pop("created_by_id", None)
    created_by_name = validated_data.pop("created_by_name", None)

    updated_by_id = validated_data.pop("updated_by_id", None)
    updated_by_name = validated_data.pop("updated_by_name", None)

    lead = Lead.objects.create(
        clinic=clinic,
        department=department,
        campaign=campaign,

        assigned_to_id=assigned_to_id,
        assigned_to_name=assigned_to_name,

        personal_id=personal_id,
        personal_name=personal_name,

        created_by_id=created_by_id,
        created_by_name=created_by_name,

        updated_by_id=updated_by_id,
        updated_by_name=updated_by_name,

        **validated_data
    )

    # Save documents
    for file_object in documents:
        LeadDocument.objects.create(
            lead=lead,
            file=file_object
        )

    return lead


# =====================================================
# UPDATE LEAD
# =====================================================
@transaction.atomic
def update_lead(instance, validated_data):

    documents = validated_data.pop("documents", [])

    IMMUTABLE_FIELDS = {
        "clinic",
        "department",
        "campaign",
        "clinic_id",
        "department_id",
        "campaign_id",
    }

    for field_name, field_value in validated_data.items():
        if field_name in IMMUTABLE_FIELDS:
            continue
        if hasattr(instance, field_name):
            setattr(instance, field_name, field_value)

    instance.save()

    # Add new documents
    for file_object in documents:
        LeadDocument.objects.create(
            lead=instance,
            file=file_object
        )

    instance.refresh_from_db()
    return instance


# =====================================================
# CLEAN EMAIL BODY
# =====================================================
def _clean_email_body(text: str) -> str:

    if not text:
        return ""

    decoded_text = (
        text
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("&nbsp;", " ")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )

    plain_text = strip_tags(decoded_text)

    import re as regex
    plain_text = regex.sub(r"\n{3,}", "\n\n", plain_text)

    return plain_text.strip()


# =====================================================
# SEND EMAIL
# =====================================================
@transaction.atomic
def send_lead_email(email_id):

    email_object = get_object_or_404(LeadEmail, id=email_id)

    # Prevent duplicate sending
    if email_object.status == "SENT":
        raise Exception("Email already sent")

    if not email_object.lead.email:
        raise Exception("Lead does not have a valid email address")

    try:
        plain_body_text = _clean_email_body(email_object.email_body)

        send_mail(
            subject=email_object.subject,
            message=plain_body_text,
            from_email=email_object.sender_email,
            recipient_list=[email_object.lead.email],
            fail_silently=False,
        )

        email_object.email_body = plain_body_text
        email_object.status = "SENT"
        email_object.sent_at = timezone.now()
        email_object.failed_reason = None
        email_object.save(
            update_fields=["email_body", "status", "sent_at", "failed_reason"]
        )

        return email_object

    except Exception as exception:
        email_object.status = "FAILED"
        email_object.failed_reason = str(exception)
        email_object.save(update_fields=["status", "failed_reason"])

        raise exception