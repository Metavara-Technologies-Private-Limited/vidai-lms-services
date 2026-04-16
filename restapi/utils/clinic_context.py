# restapi/utils/clinic_context.py

from __future__ import annotations
from typing import Optional
from rest_framework.exceptions import ValidationError
from restapi.models import Clinic


def _to_int(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def get_requested_clinic_id(request) -> Optional[int]:

    # query param
    if hasattr(request, "query_params"):
        clinic_id = _to_int(request.query_params.get("clinic_id"))
        if clinic_id:
            return clinic_id

    # header
    if hasattr(request, "headers"):
        clinic_id = _to_int(request.headers.get("X-Clinic-Id"))
        if clinic_id:
            return clinic_id

    # body
    if hasattr(request, "data"):
        clinic_id = _to_int(request.data.get("clinic_id"))
        if clinic_id:
            return clinic_id

    return None


def resolve_request_clinic(request):

    user = getattr(request, "user", None)

    if not user:
        raise ValidationError("Invalid user")

    clinic_id = get_requested_clinic_id(request)

    if not clinic_id:
        raise ValidationError({"clinic_id": "clinic_id is required"})

    clinic = Clinic.objects.filter(id=clinic_id).first()

    if not clinic:
        raise ValidationError({"clinic_id": "Invalid clinic_id"})

    return clinic


def ensure_object_in_request_clinic(request, obj_clinic):

    clinic = resolve_request_clinic(request)

    if not obj_clinic:
        raise ValidationError({"clinic": "Object has no clinic"})

    if obj_clinic.id != clinic.id:
        raise ValidationError({"clinic": "Access denied for this clinic"})