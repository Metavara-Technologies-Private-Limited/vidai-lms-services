from restapi.models import RolePermission


def _build_permission_result(permissions):
    """Build the nested permission dict from a queryset of permission objects."""
    result = {}

    for perm in permissions:
        module = normalize_role_name(perm.module_key)
        category = normalize_role_name(perm.category_key)
        subcategory = normalize_role_name(perm.subcategory_key)

        result.setdefault(module, {})

        # SETTINGS CATEGORY ROW (no subcategory) — store flags on the settings entry directly
        if category == "settings" and not subcategory:
            existing = result[module].setdefault(
                "settings",
                {
                    "can_view": False,
                    "can_add": False,
                    "can_edit": False,
                    "can_print": False,
                },
            )

        # SETTINGS WITH SUBCATEGORY — nest under settings[subcategory]
        elif category == "settings" and subcategory:
            result[module].setdefault("settings", {})
            existing = result[module]["settings"].setdefault(
                subcategory,
                {
                    "can_view": False,
                    "can_add": False,
                    "can_edit": False,
                    "can_print": False,
                },
            )

        # PURE SUBCATEGORY ROWS (category="_") — use subcategory as the key so
        # the frontend can extract the label (e.g. "integration", "tickets")
        elif category == "_" and subcategory:
            existing = result[module].setdefault(
                subcategory,
                {
                    "can_view": False,
                    "can_add": False,
                    "can_edit": False,
                    "can_print": False,
                },
            )

        # OTHER MODULES / CATEGORIES
        else:
            existing = result[module].setdefault(
                category,
                {
                    "can_view": False,
                    "can_add": False,
                    "can_edit": False,
                    "can_print": False,
                },
            )

        # MERGE permissions
        existing["can_view"] |= perm.can_view
        existing["can_add"] |= perm.can_add
        existing["can_edit"] |= perm.can_edit
        existing["can_print"] |= perm.can_print

    return result


# =========================
# NORMALIZE
# =========================
def normalize_role_name(value):
    if not value:
        return ""
    normalized = str(value).strip().lower()

    # Keep sentinel underscore keys intact (module/category placeholders).
    if normalized == "_":
        return "_"

    return normalized.replace("-", " ").replace("_", " ")


# =========================
# GET USER ROLE
# =========================
def get_user_role(user):
    if not user:
        return None

    try:
        return getattr(user.profile, "role", None)
    except Exception:
        return None


# =========================
# SUPER ADMIN CHECK
# =========================
def is_super_admin_role(role):
    if not role:
        return False

    normalized = normalize_role_name(getattr(role, "name", ""))
    return normalized in {"super admin", "superadmin"}


# =========================
# GET USER PERMISSIONS (FINAL)
# =========================
def get_user_permissions(user):
    from restapi.models.user_permission import UserPermission

    # Check for individual user-level permission overrides first
    individual_perms = UserPermission.objects.filter(user=user)
    if individual_perms.exists():
        return _build_permission_result(individual_perms)

    # Fall back to role-based permissions
    role = get_user_role(user)
    if not role:
        return {}

    permissions = RolePermission.objects.filter(role=role)
    return _build_permission_result(permissions)


# =========================
# HAS PERMISSION
# =========================
def has_permission(user, module, category, action):
    role = get_user_role(user)

    if is_super_admin_role(role):
        return True

    if action not in {"view", "add", "edit", "print"}:
        return False

    module = normalize_role_name(module)
    category = normalize_role_name(category)

    permissions = get_user_permissions(user)

    try:
        return permissions[module][category].get(f"can_{action}", False)
    except KeyError:
        return False


# =========================
# HAS SUBCATEGORY PERMISSION
# =========================
def has_subcategory_permission(user, module, category, subcategory, action):
    role = get_user_role(user)

    if is_super_admin_role(role):
        return True

    if action not in {"view", "add", "edit", "print"}:
        return False

    module = normalize_role_name(module)
    category = normalize_role_name(category)
    subcategory = normalize_role_name(subcategory)

    permissions = get_user_permissions(user)

    try:
        return permissions[module][category][subcategory].get(f"can_{action}", False)
    except KeyError:
        return False


# =========================
# LABEL BASED PERMISSION (REQUIRED)
# =========================
def has_action_permission_for_labels(user, action, labels):
    from restapi.models.user_permission import UserPermission

    if action not in {"view", "add", "edit", "print"}:
        return False

    role = get_user_role(user)

    # SUPER ADMIN → FULL ACCESS
    if is_super_admin_role(role):
        return True

    if not role:
        return False

    normalized_labels = set()

    for label in labels or []:
        normalized = normalize_role_name(label)
        if not normalized or normalized == "_":
            continue

        normalized_labels.add(normalized)

        # handle singular/plural
        if normalized.endswith("s"):
            normalized_labels.add(normalized[:-1])
        else:
            normalized_labels.add(f"{normalized}s")

    # Check individual user-level permissions first (overrides role)
    individual_perms = UserPermission.objects.filter(user=user)
    if individual_perms.exists():
        for perm in individual_perms:
            if not getattr(perm, f"can_{action}", False):
                continue

            keys = {
                normalize_role_name(perm.module_key),
                normalize_role_name(perm.category_key),
                normalize_role_name(perm.subcategory_key),
            }
            keys.discard("")
            keys.discard("_")

            if keys & normalized_labels:
                return True

        return False  # individual perms exist but none matched → deny

    # Fall back to role-based permissions
    role_perms = RolePermission.objects.filter(role=role)

    for perm in role_perms:
        if not getattr(perm, f"can_{action}", False):
            continue

        keys = {
            normalize_role_name(perm.module_key),
            normalize_role_name(perm.category_key),
            normalize_role_name(perm.subcategory_key),
        }

        keys.discard("")
        keys.discard("_")

        if keys & normalized_labels:
            return True

    return False


# =========================
# FILTER BY CLINIC (FINAL FIX)
# =========================
def filter_by_clinic(queryset, request):
    user = request.user

    if not user or not hasattr(user, "profile") or not user.profile:
        return queryset.none()

    clinic_id = request.query_params.get("clinic_id") or request.headers.get(
        "X-Clinic-Id"
    )

    # ✅ If clinic passed → allow ALL roles
    if clinic_id and str(clinic_id).isdigit():
        return queryset.filter(profile__clinic_id=int(clinic_id))

    # ✅ fallback → user clinic
    if user.profile.clinic_id:
        return queryset.filter(profile__clinic_id=user.profile.clinic_id)

    return queryset.none()
