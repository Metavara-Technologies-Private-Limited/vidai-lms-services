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
    Employee,
    Campaign,
    LeadDocument,
    LeadEmail,
)

# ✅ IMPORT
from restapi.models import ReferralSource


def _resolve_assignee_name(assigned_to_id, assigned_to_name):
    if isinstance(assigned_to_name, str):
        normalized_name = assigned_to_name.strip()
        if normalized_name:
            return normalized_name

    if assigned_to_id is None:
        return None

    employee = Employee.objects.filter(id=assigned_to_id).only("emp_name").first()
    if employee and employee.emp_name:
        return employee.emp_name

    return None


# =====================================================
# CREATE LEAD (FIXED)
# =====================================================
@transaction.atomic
def create_lead(validated_data, request=None):

    documents = validated_data.pop("documents", [])

    clinic_id = None
    if request:
        clinic_id = request.headers.get("X-Clinic-Id") or request.data.get("clinic_id")

    if not clinic_id:
        raise ValidationError({"clinic": "Clinic is required"})

    try:
        clinic = Clinic.objects.get(id=clinic_id)
    except Clinic.DoesNotExist:
        raise ValidationError({"clinic": "Invalid clinic"})

    validated_data.pop("clinic_id", None)

    # =====================================================
    # DEPARTMENT
    # =====================================================
    raw_department_id = validated_data.pop("department_id", None)
    department = None

    if raw_department_id:
        department = Department.objects.filter(
            id=raw_department_id,
            clinic=clinic,
            is_active=True,
        ).first()

    if department is None:
        department = Department.objects.filter(
            clinic=clinic,
            is_active=True,
        ).first()

    if department is None:
        department = Department.objects.create(
            clinic=clinic,
            name="General",
            is_active=True,
        )

    # =====================================================
    # CAMPAIGN
    # =====================================================
    campaign = None
    campaign_id = validated_data.pop("campaign_id", None)
    if campaign_id:
        campaign = Campaign.objects.filter(
            id=campaign_id,
            clinic=clinic
        ).first()

    # =====================================================
    # 🔥 FIXED REFERRAL SOURCE
    # =====================================================
    referral_source_id = validated_data.pop("referral_source", None)

    referral_source = None
    if referral_source_id:
        referral_source = ReferralSource.objects.filter(
            id=referral_source_id   # ✅ FIXED HERE (removed clinic filter)
        ).first()

    # =====================================================
    # ASSIGNEE
    # =====================================================
    assigned_to_id = validated_data.pop("assigned_to_id", None)
    assigned_to_name = _resolve_assignee_name(
        assigned_to_id,
        validated_data.pop("assigned_to_name", None),
    )

    personal_id = validated_data.pop("personal_id", None)
    personal_name = validated_data.pop("personal_name", None)

    created_by_id = validated_data.pop("created_by_id", None)
    created_by_name = validated_data.pop("created_by_name", None)

    updated_by_id = validated_data.pop("updated_by_id", None)
    updated_by_name = validated_data.pop("updated_by_name", None)

    # =====================================================
    # CREATE LEAD
    # =====================================================
    lead = Lead.objects.create(
        clinic=clinic,
        department=department,
        campaign=campaign,

        referral_source=referral_source,  # ✅ working now

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

    # =====================================================
    # DOCUMENTS
    # =====================================================
    for file_object in documents:
        LeadDocument.objects.create(
            lead=lead,
            file=file_object
        )

    return lead


# =====================================================
# UPDATE LEAD (UNCHANGED)
# =====================================================
@transaction.atomic
def update_lead(instance, validated_data):

    documents = validated_data.pop("documents", [])
    assigned_to_id_provided = "assigned_to_id" in validated_data
    assigned_to_name_provided = "assigned_to_name" in validated_data

    if assigned_to_id_provided:
        assigned_to_id = validated_data.pop("assigned_to_id")
        assigned_to_name = validated_data.pop("assigned_to_name", None)
        instance.assigned_to_id = assigned_to_id
        instance.assigned_to_name = _resolve_assignee_name(
            assigned_to_id,
            assigned_to_name,
        )
    elif assigned_to_name_provided:
        instance.assigned_to_name = _resolve_assignee_name(
            instance.assigned_to_id,
            validated_data.pop("assigned_to_name"),
        )

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

    for file_object in documents:
        LeadDocument.objects.create(
            lead=instance,
            file=file_object
        )

    instance.refresh_from_db()
    return instance


# =====================================================
# CLEAN EMAIL BODY (UNCHANGED)
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
# SEND EMAIL (UNCHANGED)
# =====================================================
@transaction.atomic
def send_lead_email(email_id):

    email_object = get_object_or_404(LeadEmail, id=email_id)

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