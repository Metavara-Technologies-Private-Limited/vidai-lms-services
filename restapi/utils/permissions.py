from restapi.models import RolePermission


def normalize_role_name(role_name):
    if not role_name:
        return ""
    return str(role_name).strip().lower().replace("-", " ").replace("_", " ")


def is_super_admin_role(role):
    if not role:
        return False

    normalized = normalize_role_name(getattr(role, "name", ""))
    return normalized in {"super admin", "superadmin"}


def get_user_role(user):
    if not user:
        return None

    try:
        profile = getattr(user, "profile", None)
    except Exception:
        return None

    if not profile:
        return None

    try:
        return getattr(profile, "role", None)
    except Exception:
        return None


# =========================
# GET USER PERMISSIONS
# =========================
def get_user_permissions(user):
    role = get_user_role(user)
    if not role:
        return {}

    permissions = RolePermission.objects.filter(role=role)
    result = {}

    for perm in permissions:
        module = perm.module_key
        category = perm.category_key
        subcategory = perm.subcategory_key

        if module not in result:
            result[module] = {}

        # SETTINGS (WITH SUBCATEGORY)
        if category.lower() == "settings":

            if category not in result[module]:
                result[module][category] = {}

            if not subcategory:
                continue

            if subcategory not in result[module][category]:
                result[module][category][subcategory] = []

            result[module][category][subcategory].append(
                {
                    "can_view": perm.can_view,
                    "can_add": perm.can_add,
                    "can_edit": perm.can_edit,
                    "can_print": perm.can_print,
                }
            )

        # OTHER MODULES
        else:

            if category not in result[module]:
                result[module][category] = []

            result[module][category].append(
                {
                    "can_view": perm.can_view,
                    "can_add": perm.can_add,
                    "can_edit": perm.can_edit,
                    "can_print": perm.can_print,
                }
            )

    return result


# =========================
# CHECK PERMISSION
# =========================
def has_permission(user, module, category, action):
    role = get_user_role(user)

    # SUPER ADMIN -> FULL ACCESS
    if is_super_admin_role(role):
        return True

    if action not in {"view", "add", "edit", "print"}:
        return False

    if not role:
        return False

    module_norm = normalize_role_name(module)
    category_norm = normalize_role_name(category)

    permissions = RolePermission.objects.filter(role=role)

    for perm in permissions:
        module_key = normalize_role_name(perm.module_key)
        category_key = normalize_role_name(perm.category_key)

        module_match = module_key in {module_norm, "_", ""}
        category_match = category_key in {category_norm, "_", ""}

        if not (module_match and category_match):
            continue

        if getattr(perm, f"can_{action}", False):
            return True

    return False


def has_subcategory_permission(user, module, category, subcategory, action):
    if action not in {"view", "add", "edit", "print"}:
        return False

    role = get_user_role(user)

    # SUPER ADMIN -> FULL ACCESS
    if is_super_admin_role(role):
        return True

    if not role:
        return False

    module_norm = normalize_role_name(module)
    category_norm = normalize_role_name(category)
    subcategory_norm = normalize_role_name(subcategory)
    sub_aliases = {subcategory_norm}
    if subcategory_norm.endswith("s"):
        sub_aliases.add(subcategory_norm[:-1])
    else:
        sub_aliases.add(f"{subcategory_norm}s")

    permissions = RolePermission.objects.filter(role=role)

    for perm in permissions:
        module_key = normalize_role_name(perm.module_key)
        category_key = normalize_role_name(perm.category_key)
        sub_key = normalize_role_name(perm.subcategory_key)

        module_match = module_key in {module_norm, "_", ""}
        category_match = category_key in {category_norm, "_", ""}
        sub_match = sub_key in sub_aliases

        if not (module_match and category_match and sub_match):
            continue

        if getattr(perm, f"can_{action}", False):
            return True

    return False


def has_action_permission_for_labels(user, action, labels):
    if action not in {"view", "add", "edit", "print"}:
        return False

    role = get_user_role(user)
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
        if normalized.endswith("s"):
            normalized_labels.add(normalized[:-1])
        else:
            normalized_labels.add(f"{normalized}s")

    if not normalized_labels:
        return False

    permissions = RolePermission.objects.filter(role=role)

    for perm in permissions:
        if not getattr(perm, f"can_{action}", False):
            continue

        keys = {
            normalize_role_name(getattr(perm, "module_key", "")),
            normalize_role_name(getattr(perm, "category_key", "")),
            normalize_role_name(getattr(perm, "subcategory_key", "")),
        }
        keys.discard("")
        keys.discard("_")

        if keys & normalized_labels:
            return True

    return False


# =========================
# FILTER QUERYSET BY CLINIC
# =========================
def filter_by_clinic(queryset, user):
    role = get_user_role(user)

    if role:
        if is_super_admin_role(role):
            return queryset

        try:
            clinic = getattr(user.profile, "clinic", None)
        except Exception:
            clinic = None

        return queryset.filter(profile__clinic=clinic)

    return queryset.none()