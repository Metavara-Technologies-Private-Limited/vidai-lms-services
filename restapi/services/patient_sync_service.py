import logging
import requests

from django.conf import settings
from restapi.models.lead import Lead
from django.utils import timezone

logger = logging.getLogger(__name__)


def split_name(full_name):
    if not full_name:
        return "", ""

    parts = full_name.strip().split()

    if len(parts) == 1:
        return parts[0], ""

    return parts[0], " ".join(parts[1:])


def get_external_access_token():
    print("=== Requesting External Access Token ===")
    response = requests.post(
        f"{settings.EXTERNAL_PATIENT_BASE_URL}/api/login/",
        json={
            "username": settings.EXTERNAL_PATIENT_USERNAME,
            "password": settings.EXTERNAL_PATIENT_PASSWORD,
        },
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()
    print("=== Token Response ===", data)

    token = data.get("access")

    if not token:
        raise Exception("Access token missing in response")

    return token


def build_patient_payload(lead):
    first_name, last_name = split_name(lead.full_name)

    payload = {
        "clinic": settings.EXTERNAL_PATIENT_CLINIC_ID,
        "first_name": first_name,
        "last_name": last_name,
        "gender": (lead.gender or "MALE").upper(),
        "mobile_number": lead.contact_no or "",
        "patient_type": "PATIENT_COUPLE",
    }

    dob = getattr(lead, "date_of_birth", None)

    payload["date_of_birth"] = str(
        dob if dob else "1995-01-01"
    )

    # PARTNER SUPPORT
    if lead.partner_inquiry and lead.partner_full_name:

        p_first, p_last = split_name(lead.partner_full_name)

        payload["is_new"] = True

        payload["partner"] = {
            "first_name": p_first,
            "last_name": p_last,
            "gender": (lead.partner_gender or "").upper(),
            "mobile_number": lead.contact_no or "",
            "patient_type": "PATIENT_COUPLE",
        }

    return payload


def sync_patient_to_external_system(lead):

    token = get_external_access_token()

    payload = build_patient_payload(lead)

    response = requests.post(
        f"{settings.EXTERNAL_PATIENT_BASE_URL}/api/patients/",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    lead.external_patient_id = data.get("id")

    lead.external_patient_sync_error = None

    lead.external_patient_synced_at = timezone.now()

    lead.save(
        update_fields=[
            "external_patient_id",
            "external_patient_synced_at",
            "external_patient_sync_error",
        ]
    )

    logger.info(
        "External patient sync success | Lead=%s | Patient=%s",
        lead.id,
        data.get("id"),
    )

    return data
