from restapi.models import RolePermission
from restapi.utils.clinic_context import resolve_request_clinic


# =========================
# NORMALIZE ROLE NAME
# =========================
def normalize_role_name(role_name):
    return str(role_name or "").strip().lower().replace("-", " ").replace("_", " ")


# =========================
# SUPER ADMIN CHECK
# =========================
def is_super_admin_role(role):
    return normalize_role_name(getattr(role, "name", "")) in {"super admin", "superadmin"}


# =========================
# GET USER ROLE
# =========================
def get_user_role(user):
    profile = getattr(user, "profile", None)
    return getattr(profile, "role", None) if profile else None


# =========================
# GET ROLE PERMISSIONS (OPTIMIZED)
# =========================
def _get_role_permissions(role):
    if not role:
        return RolePermission.objects.none()
    return RolePermission.objects.filter(role=role)


# =========================
# FINAL PERMISSIONS
# =========================
def get_user_permissions(user):
    role = get_user_role(user)

    permissions = (
        RolePermission.objects.all()
        if is_super_admin_role(role)
        else _get_role_permissions(role)
    )

    result = {}

    for perm in permissions:
        module = perm.module_key or "default"
        category = perm.category_key or "default"
        subcategory = perm.subcategory_key

        result.setdefault(module, {})

        if category.lower() == "settings":
            result[module].setdefault("settings", {})

            if not subcategory:
                continue

            result[module]["settings"].setdefault(subcategory, [{
                "can_view": False,
                "can_add": False,
                "can_edit": False,
                "can_print": False,
            }])

            obj = result[module]["settings"][subcategory][0]

        else:
            result[module].setdefault(category, [{
                "can_view": False,
                "can_add": False,
                "can_edit": False,
                "can_print": False,
            }])

            obj = result[module][category][0]

        obj["can_view"] |= perm.can_view
        obj["can_add"] |= perm.can_add
        obj["can_edit"] |= perm.can_edit
        obj["can_print"] |= perm.can_print

    return result


# =========================
# CHECK PERMISSION
# =========================
def has_permission(user, module, category, action):
    if action not in {"view", "add", "edit", "print"}:
        return False

    role = get_user_role(user)

    if is_super_admin_role(role):
        return True

    permissions = _get_role_permissions(role)

    module_norm = normalize_role_name(module)
    category_norm = normalize_role_name(category)

    return any(
        normalize_role_name(p.module_key) in {module_norm, "_", ""}
        and normalize_role_name(p.category_key) in {category_norm, "_", ""}
        and getattr(p, f"can_{action}", False)
        for p in permissions
    )


# =========================
# SUBCATEGORY PERMISSION
# =========================
def has_subcategory_permission(user, module, category, subcategory, action):
    if action not in {"view", "add", "edit", "print"}:
        return False

    role = get_user_role(user)

    if is_super_admin_role(role):
        return True

    permissions = _get_role_permissions(role)

    module_norm = normalize_role_name(module)
    category_norm = normalize_role_name(category)
    sub_norm = normalize_role_name(subcategory)

    return any(
        normalize_role_name(p.module_key) in {module_norm, "_", ""}
        and normalize_role_name(p.category_key) in {category_norm, "_", ""}
        and normalize_role_name(p.subcategory_key) == sub_norm
        and getattr(p, f"can_{action}", False)
        for p in permissions
    )


# =========================
# LABEL PERMISSION
# =========================
def has_action_permission_for_labels(user, action, labels):
    if action not in {"view", "add", "edit", "print"}:
        return False

    role = get_user_role(user)

    if is_super_admin_role(role):
        return True

    permissions = _get_role_permissions(role)

    normalized_labels = {
        normalize_role_name(label)
        for label in (labels or [])
        if normalize_role_name(label)
    }

    return any(
        getattr(p, f"can_{action}", False)
        and {
            normalize_role_name(p.module_key),
            normalize_role_name(p.category_key),
            normalize_role_name(p.subcategory_key),
        } & normalized_labels
        for p in permissions
    )


# =========================
# FINAL CLINIC FILTER
# =========================
def filter_by_clinic(queryset, request):
    """
    🔥 FINAL ARCHITECTURE:
    - All roles can switch clinics
    - Data is always isolated by selected clinic
    """

    try:
        clinic = resolve_request_clinic(request)
    except Exception:
        return queryset.none()

    model = queryset.model

    if model.__name__ == "User":
        return queryset.filter(profile__clinic=clinic)

    if model.__name__ == "UserProfile":
        return queryset.filter(clinic=clinic)

    if hasattr(model, "clinic"):
        return queryset.filter(clinic=clinic)

    return queryset.none()