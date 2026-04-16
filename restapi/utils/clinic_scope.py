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


def get_user_clinic(user) -> Optional[Clinic]:
    profile = getattr(user, "profile", None)
    if not profile:
        return None
    return getattr(profile, "clinic", None)


# =========================
# ✅ FINAL FIXED FUNCTION
# =========================
def resolve_request_clinic(request, required: bool = True) -> Optional[Clinic]:
    user = getattr(request, "user", None)
    profile = getattr(user, "profile", None)
    user_role = getattr(profile, "role", None)
    user_clinic = get_user_clinic(user)
    requested_clinic_id = get_requested_clinic_id(request)

    # -----------------------------
    # ✅ If clinic passed in request
    # -----------------------------
    if requested_clinic_id:
        clinic = Clinic.objects.filter(id=requested_clinic_id).first()

        if clinic is None:
            raise ValidationError({"clinic_id": "Invalid clinic_id"})

        # ✅ Super Admin → full access
        if is_super_admin_role(user_role):
            return clinic

        # ✅ Admin/User → allow switching (NO HARD BLOCK)
        return clinic

    # -----------------------------
    # ✅ Fallback → user's own clinic
    # -----------------------------
    if user_clinic is not None:
        return user_clinic

    if required:
        raise ValidationError({"clinic_id": "Clinic is required"})

    return None


# =========================
# ✅ SAFE OBJECT CHECK
# =========================
def ensure_object_in_request_clinic(request, object_clinic: Optional[Clinic]) -> None:
    if object_clinic is None:
        raise ValidationError({"clinic_id": "Object has no clinic"})

    requested_clinic_id = get_requested_clinic_id(request)

    # ✅ If request clinic is given → must match object
    if requested_clinic_id and object_clinic.id != requested_clinic_id:
        raise ValidationError({"clinic_id": "Object does not belong to requested clinic"})

    # ✅ NO restriction for admin/user (fix)
    return