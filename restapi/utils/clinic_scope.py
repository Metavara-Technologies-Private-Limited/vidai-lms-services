from __future__ import annotations

from typing import Optional

from rest_framework.exceptions import ValidationError

from restapi.models import Clinic
from restapi.utils.permissions import is_super_admin_role


def _to_int(value: object) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


# =========================
# GET CLINIC FROM REQUEST
# =========================
def get_requested_clinic_id(request) -> Optional[int]:
    query_params = getattr(request, "query_params", None)
    if query_params is not None:
        for key in ("clinic_id", "clinic"):
            clinic_id = _to_int(query_params.get(key))
            if clinic_id:
                return clinic_id

    headers = getattr(request, "headers", None)
    if headers is not None:
        clinic_id = _to_int(headers.get("X-Clinic-Id"))
        if clinic_id:
            return clinic_id

    data = getattr(request, "data", None)
    if data is not None:
        for key in ("clinic_id", "clinic"):
            clinic_id = _to_int(data.get(key))
            if clinic_id:
                return clinic_id

    return None


# =========================
# GET USER DEFAULT CLINIC
# =========================
def get_user_clinic(user) -> Optional[Clinic]:
    profile = getattr(user, "profile", None)
    if not profile:
        return None
    return getattr(profile, "clinic", None)


# =========================
# ✅ FINAL FIXED (ALLOW ALL ROLES TO SWITCH)
# =========================
def resolve_request_clinic(request, required: bool = True) -> Optional[Clinic]:
    user = getattr(request, "user", None)
    user_clinic = get_user_clinic(user)
    requested_clinic_id = get_requested_clinic_id(request)

    # ✅ If clinic passed → allow for ALL roles
    if requested_clinic_id:
        clinic = Clinic.objects.filter(id=requested_clinic_id).first()

        if clinic is None:
            raise ValidationError({"clinic_id": "Invalid clinic_id"})

        return clinic

    # ✅ fallback → user's own clinic
    if user_clinic is not None:
        return user_clinic

    if required:
        raise ValidationError({"clinic_id": "Clinic is required"})

    return None


# =========================
# ✅ FINAL SAFE OBJECT CHECK
# =========================
def ensure_object_in_request_clinic(request, object_clinic: Optional[Clinic]) -> None:
    if object_clinic is None:
        raise ValidationError({"clinic_id": "Object has no clinic"})

    requested_clinic_id = get_requested_clinic_id(request)

    # ✅ Ensure object belongs to selected clinic
    if requested_clinic_id and object_clinic.id != requested_clinic_id:
        raise ValidationError({"clinic_id": "Object does not belong to requested clinic"})

    # ✅ NO ROLE RESTRICTION (Admin/User can switch now)
    return