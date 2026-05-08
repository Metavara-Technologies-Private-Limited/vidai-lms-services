# =====================================================
# Imports
# =====================================================
import logging
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.html import strip_tags
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from restapi.models import Interest
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
    PipelineStage,
)

logger = logging.getLogger(__name__)

# =====================================================
# ACTION STATUS VALIDATION
# =====================================================
_VALID_ACTION_STATUSES = {
    "to_do",
    "in_progress",
    "completed"
}


# =====================================================
# HELPER: NORMALIZE ACTION STATUS
# =====================================================
def _normalize_action_status(value):

    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip().lower()

    if value == "" or value == "null":
        return None

    if value not in _VALID_ACTION_STATUSES:
        raise ValidationError({
            "action_status":
            f"Invalid value '{value}'. "
            f"Must be one of: {', '.join(sorted(_VALID_ACTION_STATUSES))}"
        })

    return value


# =====================================================
# HELPER: USER INFO
# =====================================================
def _get_user_info(request):
    if not request:
        return None, "System"

    user = request.user

    if hasattr(user, "employee") and user.employee:
        return user.employee.id, user.employee.emp_name

    return user.id, str(user)


# =====================================================
# HELPER: ASSIGNEE NAME
# =====================================================
def _resolve_assignee_name(assigned_to_id, assigned_to_name):
    if isinstance(assigned_to_name, str) and assigned_to_name.strip():
        return assigned_to_name.strip()

    if assigned_to_id:
        employee = Employee.objects.filter(id=assigned_to_id).only("emp_name").first()
        if employee:
            return employee.emp_name

    return None


# =====================================================
# PHONE VALIDATION
# =====================================================
def _validate_phone(value):

    if value is None:
        return None

    value = str(value).strip()

    if value == "" or value.lower() in ["null", "none"]:
        return None

    if value in ["0", "00", "000", "0000000000"]:
        return None

    value = value.replace(" ", "")

    # INTERNATIONAL
    if value.startswith("+"):
        digits = value[1:]

        if not digits.isdigit():
            raise ValidationError({"contact_no": "Invalid international phone number"})

        if len(digits) < 7 or len(digits) > 15:
            raise ValidationError({"contact_no": "Invalid international phone number"})

        return value

    # INDIA
    if value.startswith("+91"):
        value = value[3:]
    elif value.startswith("91") and len(value) == 12:
        value = value[2:]

    if not value.isdigit():
        raise ValidationError({"contact_no": "Phone must contain digits only"})

    if not (7 <= len(value) <= 15):
        raise ValidationError({"contact_no": "Phone number must be between 7 and 15 digits"})

    invalid_numbers = {
        "1111111111","2222222222","3333333333","4444444444",
        "5555555555","6666666666","7777777777","8888888888",
        "9999999999","1234567890","0123456789"
    }

    if value in invalid_numbers:
        raise ValidationError({"contact_no": "Invalid phone number"})

    return value


# =====================================================
# CREATE LEAD
# =====================================================
@transaction.atomic
def create_lead(validated_data, request=None):

    documents = validated_data.pop("documents", [])

    # ✅ INTEREST
    treatment_interest = validated_data.pop("treatment_interest", [])

    # ✅ DOCUMENT SAFETY
    if not isinstance(documents, list):
        documents = []

    # =====================================================
    # PHONE VALIDATION
    # =====================================================
    validated_data["contact_no"] = _validate_phone(
        validated_data.get("contact_no")
    )

    # =====================================================
    # ACTION STATUS
    # =====================================================
    if "action_status" in validated_data:
        validated_data["action_status"] = _normalize_action_status(
            validated_data["action_status"]
        )

    # =====================================================
    # CLINIC
    # =====================================================
    clinic_id = request.headers.get("X-Clinic-Id") if request else None

    if not clinic_id:
        raise ValidationError({"clinic": "Clinic is required"})

    clinic = get_object_or_404(Clinic, id=clinic_id)

    validated_data.pop("clinic_id", None)
    validated_data.pop("created_by_id", None)
    validated_data.pop("created_by_name", None)

    created_by_id, created_by_name = _get_user_info(request)

    # =====================================================
    # STAGE
    # =====================================================
    stage_id = validated_data.pop("stage_id", None)

    stage = None

    if stage_id:

        stage = PipelineStage.objects.filter(
            id=stage_id,
            is_active=True,
            is_deleted=False,
            pipeline__clinic=clinic
        ).select_related("pipeline").first()

        if not stage:
            raise ValidationError({"stage_id": "Invalid stage"})

    # =====================================================
    # OPTIONAL DEPARTMENT FIX
    # =====================================================
    department = None

    department_id = validated_data.pop("department_id", None)

    if department_id:

        department = Department.objects.filter(
            id=department_id,
            clinic=clinic,
            is_active=True
        ).first()

        if not department:
            raise ValidationError({
                "department_id": "Invalid department for this clinic"
            })

    # =====================================================
    # CAMPAIGN
    # =====================================================
    campaign_id = validated_data.pop("campaign_id", None)

    campaign = Campaign.objects.filter(
        id=campaign_id,
        clinic=clinic
    ).first() if campaign_id else None

    # =====================================================
    # ASSIGNED TO
    # =====================================================
    assigned_to_id = validated_data.pop("assigned_to_id", None)

    assigned_to_name = _resolve_assignee_name(
        assigned_to_id,
        validated_data.pop("assigned_to_name", None)
    )

    # =====================================================
    # REFERRAL
    # =====================================================
    referral_department = None
    referral_source = None

    ref_dept_id = validated_data.pop("referral_department_id", None)

    ref_source_id = validated_data.pop("referral_source_id", None)

    referral_source_data = validated_data.pop(
        "referral_source",
        None
    )

    if referral_source_data:

        first_name = referral_source_data.get(
            "first_name",
            ""
        ).strip()

        last_name = referral_source_data.get(
            "last_name",
            ""
        ).strip()

        email = referral_source_data.get("email")

        role = referral_source_data.get("role")

        full_name = f"{first_name} {last_name}".strip()

        if ref_dept_id:

            referral_department = ReferralDepartment.objects.filter(
                id=ref_dept_id,
                clinic=clinic,
                is_active=True
            ).first()

        elif role:

            referral_department = ReferralDepartment.objects.filter(
                name__iexact=role.strip(),
                clinic=clinic,
                is_active=True
            ).first()

        referral_source = ReferralSource.objects.filter(
            email=email,
            clinic=clinic
        ).first()

        if not referral_source:

            referral_source = ReferralSource.objects.create(
                name=full_name,
                email=email,
                clinic=clinic,
                referral_department=referral_department,
                created_by=request.user if request else None
            )

    else:

        if ref_source_id and not ref_dept_id:
            raise ValidationError({
                "referral_department_id": "Required"
            })

        if ref_dept_id:

            referral_department = get_object_or_404(
                ReferralDepartment,
                id=ref_dept_id,
                clinic=clinic,
                is_active=True
            )

        if ref_source_id:

            referral_source = get_object_or_404(
                ReferralSource,
                id=ref_source_id,
                clinic=clinic
            )

            if (
                referral_department and
                referral_source.referral_department_id != referral_department.id
            ):
                raise ValidationError("Referral mismatch")

    validated_data.pop("referral_department_id", None)
    validated_data.pop("referral_source_id", None)

    # =====================================================
    # CREATE LEAD
    # =====================================================
    lead = Lead.objects.create(
        clinic=clinic,
        department=department,
        campaign=campaign,
        stage=stage,
        assigned_to_id=assigned_to_id,
        assigned_to_name=assigned_to_name,
        created_by_id=created_by_id,
        created_by_name=created_by_name,
        referral_department=referral_department,
        referral_source=referral_source,
        **validated_data
    )

    # =====================================================
    # SAVE INTERESTS
    # =====================================================
    if treatment_interest:
        # Flatten: entries may be UUIDs, names, or comma-joined UUID strings
        flat_ids = []
        for item in treatment_interest:
            if not item:
                continue
            for part in str(item).split(","):
                cleaned = part.strip()
                if cleaned:
                    flat_ids.append(cleaned)

        # Look up existing interests by UUID only — never create from IDs
        interests = Interest.objects.filter(id__in=flat_ids, clinic=clinic, is_active=True)

        if interests.count() != len(set(flat_ids)):
            found_ids = set(str(i.id) for i in interests)
            missing = [x for x in flat_ids if x not in found_ids]
            logger.warning(f"[CREATE] Some interest IDs not found: {missing}")

        lead.treatment_interest.set(interests)

    # =====================================================
    # SAVE DOCUMENTS
    # =====================================================
    for file in documents or []:

        if not file or not hasattr(file, "name"):
            continue

        logger.info(f"[CREATE] Uploading file: {file.name}")

        LeadDocument.objects.create(
            lead=lead,
            file=file
        )

    return lead


# =====================================================
# UPDATE LEAD
# =====================================================
@transaction.atomic
def update_lead(instance, validated_data, request=None):

    documents = validated_data.pop("documents", [])

    # ✅ INTEREST
    treatment_interest = validated_data.pop("treatment_interest", None)

    # ✅ SAFETY FIX
    if treatment_interest in ["", "null"]:
        treatment_interest = []

    # ✅ DOCUMENT SAFETY
    if not isinstance(documents, list):
        documents = []

    old_status = Lead.objects.filter(id=instance.id)\
        .values_list("lead_status", flat=True).first()

    old_stage = instance.stage

    # =====================================================
    # PHONE VALIDATION
    # =====================================================
    if "contact_no" in validated_data:
        validated_data["contact_no"] = _validate_phone(
            validated_data.get("contact_no")
        )

    # =====================================================
    # ACTION STATUS
    # =====================================================
    if request and "action_status" in request.data:
        raw_action = request.data.get("action_status")

        validated_data["action_status"] = _normalize_action_status(
            raw_action
        )

    elif "action_status" in validated_data:

        validated_data["action_status"] = _normalize_action_status(
            validated_data["action_status"]
        )

    # =====================================================
    # UPDATED BY
    # =====================================================
    updated_by_id, updated_by_name = _get_user_info(request)

    instance.updated_by_id = updated_by_id
    instance.updated_by_name = updated_by_name

    # =====================================================
    # STAGE
    # =====================================================
    stage_id = validated_data.pop("stage_id", None)

    if stage_id:

        stage = PipelineStage.objects.filter(
            id=stage_id,
            is_active=True,
            is_deleted=False,
            pipeline__clinic=instance.clinic
        ).first()

        if not stage:
            raise ValidationError({"stage_id": "Invalid stage"})

        instance.stage = stage

    # =====================================================
    # OPTIONAL DEPARTMENT FIX
    # =====================================================
    if "department_id" in validated_data:

        department_id = validated_data.pop("department_id", None)

        if department_id:

            department = Department.objects.filter(
                id=department_id,
                clinic=instance.clinic,
                is_active=True
            ).first()

            if not department:
                raise ValidationError({
                    "department_id": "Invalid department for this clinic"
                })

            instance.department = department

        else:
            instance.department = None

    # =====================================================
    # ASSIGNED TO
    # =====================================================
    if "assigned_to_id" in validated_data:

        assigned_to_id = validated_data.pop("assigned_to_id")

        assigned_to_name = validated_data.pop(
            "assigned_to_name",
            None
        )

        instance.assigned_to_id = assigned_to_id

        instance.assigned_to_name = _resolve_assignee_name(
            assigned_to_id,
            assigned_to_name
        )

    # =====================================================
    # REFERRAL
    # =====================================================
    ref_dept_id = validated_data.pop("referral_department_id", None)

    ref_source_id = validated_data.pop("referral_source_id", None)

    referral_source_data = validated_data.pop(
        "referral_source",
        None
    )

    if referral_source_data:

        full_name = (
            f"{referral_source_data.get('first_name','')} "
            f"{referral_source_data.get('last_name','')}"
        ).strip()

        email = referral_source_data.get("email")
        role = referral_source_data.get("role")

        referral_department = None

        if role:
            referral_department = ReferralDepartment.objects.filter(
                name__iexact=role,
                clinic=instance.clinic,
                is_active=True
            ).first()

        referral_source = ReferralSource.objects.create(
            name=full_name,
            email=email,
            clinic=instance.clinic,
            referral_department=referral_department
        )

        instance.referral_source = referral_source
        instance.referral_department = referral_department

    else:

        if ref_dept_id:
            instance.referral_department = ReferralDepartment.objects.filter(
                id=ref_dept_id,
                clinic=instance.clinic
            ).first()

        if ref_source_id:
            instance.referral_source = ReferralSource.objects.filter(
                id=ref_source_id,
                clinic=instance.clinic
            ).first()

    # =====================================================
    # STATUS
    # =====================================================
    new_status = None

    if request and hasattr(request, "data"):
        new_status = request.data.get("lead_status")

    if not new_status:
        new_status = validated_data.get("lead_status")

    if new_status:
        new_status = str(new_status).strip().lower()

    logger.info(f"OLD STATUS: {old_status} | NEW STATUS: {new_status}")

    # =====================================================
    # CONVERSION LOGIC
    # =====================================================
    if (
        new_status == "converted" and
        str(old_status).lower() != "converted"
    ):

        instance.converted_at_stage = old_stage
        instance.converted_at_status = old_status

        conversion_stage = PipelineStage.objects.filter(
            pipeline=old_stage.pipeline if old_stage else None,
            is_conversion_stage=True,
            is_active=True,
            is_deleted=False
        ).first()

        if conversion_stage:
            instance.stage = conversion_stage

        instance.converted_at = timezone.now()

    # =====================================================
    # UPDATE FIELDS
    # =====================================================
    for field, value in validated_data.items():
        setattr(instance, field, value)

    instance.save()

    # =====================================================
    # UPDATE INTERESTS
    # =====================================================
    if treatment_interest is not None:
        # Flatten: entries may be UUIDs or comma-joined UUID strings
        flat_ids = []
        for item in treatment_interest:
            if not item:
                continue
            for part in str(item).split(","):
                cleaned = part.strip()
                if cleaned:
                    flat_ids.append(cleaned)

        if flat_ids:
            interests = Interest.objects.filter(
                id__in=flat_ids, clinic=instance.clinic, is_active=True
            )

            if interests.count() != len(set(flat_ids)):
                found_ids = set(str(i.id) for i in interests)
                missing = [x for x in flat_ids if x not in found_ids]
                logger.warning(f"[UPDATE] Some interest IDs not found: {missing}")

            instance.treatment_interest.set(interests)
        else:
            instance.treatment_interest.clear()

    # =====================================================
    # SAVE DOCUMENTS
    # =====================================================
    for file in documents or []:

        if not file or not hasattr(file, "name"):
            continue

        logger.info(f"[UPDATE] Uploading file: {file.name}")

        LeadDocument.objects.create(
            lead=instance,
            file=file
        )

    return instance


# =====================================================
# EMAIL HELPERS
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
