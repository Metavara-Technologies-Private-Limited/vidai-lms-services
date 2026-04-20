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
    ReferralDepartment,
    ReferralSource,
)


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
# CREATE LEAD
# =====================================================
@transaction.atomic
def create_lead(validated_data, request=None):

    documents = validated_data.pop("documents", [])

    # ===================== CLINIC =====================
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

    # ===================== DEPARTMENT =====================
    raw_department_id = validated_data.pop("department_id", None)

    department = None
    if raw_department_id:
        department = Department.objects.filter(
            id=raw_department_id,
            clinic=clinic,
            is_active=True
        ).first()

    if not department:
        department = Department.objects.filter(
            clinic=clinic,
            is_active=True
        ).first()

    if not department:
        department = Department.objects.create(
            clinic=clinic,
            name="General",
            is_active=True
        )

    # ===================== CAMPAIGN =====================
    campaign = None
    campaign_id = validated_data.pop("campaign_id", None)

    if campaign_id:
        campaign = Campaign.objects.filter(
            id=campaign_id,
            clinic=clinic
        ).first()

    # ===================== ASSIGNEE =====================
    assigned_to_id = validated_data.pop("assigned_to_id", None)
    assigned_to_name = _resolve_assignee_name(
        assigned_to_id,
        validated_data.pop("assigned_to_name", None)
    )

    personal_id = validated_data.pop("personal_id", None)
    personal_name = validated_data.pop("personal_name", None)

    created_by_id = validated_data.pop("created_by_id", None)
    created_by_name = validated_data.pop("created_by_name", None)

    updated_by_id = validated_data.pop("updated_by_id", None)
    updated_by_name = validated_data.pop("updated_by_name", None)

    if request:
        employee = getattr(request.user, "employee", None)
        if employee:
            if created_by_id is None:
                created_by_id = employee.id
            if not created_by_name:
                created_by_name = employee.emp_name

    # ===================== REFERRAL =====================
    referral_department = None
    referral_source = None

    ref_dept_id = validated_data.pop("referral_department_id", None)
    ref_source_id = validated_data.pop("referral_source_id", None)

    if ref_source_id and not ref_dept_id:
        raise ValidationError({
            "referral_department_id": "Required when referral_source is provided"
        })

    if ref_dept_id:
        referral_department = ReferralDepartment.objects.filter(
            id=ref_dept_id,
            clinic=clinic,
            is_active=True
        ).only("id").first()

        if not referral_department:
            raise ValidationError({"referral_department_id": "Invalid referral department"})

    if ref_source_id:
        referral_source = ReferralSource.objects.filter(
            id=ref_source_id,
            clinic=clinic
        ).only("id", "referral_department_id").first()

        if not referral_source:
            raise ValidationError({"referral_source_id": "Invalid referral source"})

        if referral_department and referral_source.referral_department_id != referral_department.pk:
            raise ValidationError("Referral Source does not belong to selected Department")

    # ===================== CREATE =====================
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

        referral_department=referral_department,
        referral_source=referral_source,

        **validated_data
    )

    # ===================== DOCUMENTS =====================
    for file_object in documents:
        LeadDocument.objects.create(lead=lead, file=file_object)

    return lead


# =====================================================
# UPDATE LEAD
# =====================================================
@transaction.atomic
def update_lead(instance, validated_data):

    documents = validated_data.pop("documents", [])

    # ===================== ASSIGNEE =====================
    if "assigned_to_id" in validated_data:
        assigned_to_id = validated_data.pop("assigned_to_id")
        assigned_to_name = validated_data.pop("assigned_to_name", None)

        instance.assigned_to_id = assigned_to_id
        instance.assigned_to_name = _resolve_assignee_name(
            assigned_to_id,
            assigned_to_name
        )

    elif "assigned_to_name" in validated_data:
        instance.assigned_to_name = _resolve_assignee_name(
            instance.assigned_to_id,
            validated_data.pop("assigned_to_name")
        )

    # ===================== REFERRAL UPDATE =====================
    ref_dept_id = validated_data.pop("referral_department_id", None)
    ref_source_id = validated_data.pop("referral_source_id", None)

    if ref_source_id and not ref_dept_id:
        raise ValidationError({
            "referral_department_id": "Required when referral_source is provided"
        })

    if ref_dept_id:
        instance.referral_department = ReferralDepartment.objects.filter(
            id=ref_dept_id,
            clinic=instance.clinic,
            is_active=True
        ).first()

    if ref_source_id:
        instance.referral_source = ReferralSource.objects.filter(
            id=ref_source_id,
            clinic=instance.clinic
        ).first()

    # ===================== UPDATE FIELDS =====================
    IMMUTABLE_FIELDS = {
        "clinic", "department", "campaign",
        "clinic_id", "department_id", "campaign_id",
    }

    for field, value in validated_data.items():
        if field not in IMMUTABLE_FIELDS and hasattr(instance, field):
            setattr(instance, field, value)

    instance.save()

    # ===================== DOCUMENTS =====================
    for file_object in documents:
        LeadDocument.objects.create(lead=instance, file=file_object)

    instance.refresh_from_db()
    return instance


# =====================================================
# CLEAN EMAIL BODY
# =====================================================
def _clean_email_body(text: str) -> str:

    if not text:
        return ""

    decoded = (
        text.replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&amp;", "&")
            .replace("&nbsp;", " ")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
    )

    plain = strip_tags(decoded)

    import re
    plain = re.sub(r"\n{3,}", "\n\n", plain)

    return plain.strip()


# =====================================================
# SEND EMAIL
# =====================================================
@transaction.atomic
def send_lead_email(email_id):

    email_obj = get_object_or_404(LeadEmail, id=email_id)

    if email_obj.status == "SENT":
        raise Exception("Email already sent")

    if not email_obj.lead.email:
        raise Exception("Lead does not have a valid email")

    try:
        body = _clean_email_body(email_obj.email_body)

        send_mail(
            subject=email_obj.subject,
            message=body,
            from_email=email_obj.sender_email,
            recipient_list=[email_obj.lead.email],
            fail_silently=False,
        )

        email_obj.email_body = body
        email_obj.status = "SENT"
        email_obj.sent_at = timezone.now()
        email_obj.failed_reason = None

        email_obj.save(update_fields=[
            "email_body", "status", "sent_at", "failed_reason"
        ])

        return email_obj

    except Exception as e:
        email_obj.status = "FAILED"
        email_obj.failed_reason = str(e)
        email_obj.save(update_fields=["status", "failed_reason"])
        raise e
