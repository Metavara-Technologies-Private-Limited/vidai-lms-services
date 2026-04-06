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


# =========================
# GET USER PERMISSIONS
# =========================
def get_user_permissions(user):

    if not hasattr(user, "profile") or not user.profile.role:
        return {}

    role = user.profile.role
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

            result[module][category][subcategory].append({
                "can_view": perm.can_view,
                "can_add": perm.can_add,
                "can_edit": perm.can_edit,
                "can_print": perm.can_print,
            })

        # OTHER MODULES
        else:

            if category not in result[module]:
                result[module][category] = []

            result[module][category].append({
                "can_view": perm.can_view,
                "can_add": perm.can_add,
                "can_edit": perm.can_edit,
                "can_print": perm.can_print,
            })

    return result


# =========================
# CHECK PERMISSION
# =========================
def has_permission(user, module, category, action):

    # SUPER ADMIN → FULL ACCESS
    if hasattr(user, "profile") and user.profile.role:
        if is_super_admin_role(user.profile.role):
            return True

    permissions = get_user_permissions(user)

    if module not in permissions:
        return False

    if category not in permissions[module]:
        return False

    for perm in permissions[module][category]:
        if perm.get(f"can_{action}"):
            return True

    return False


# =========================
# FILTER QUERYSET BY CLINIC
# =========================
def filter_by_clinic(queryset, user):

    if hasattr(user, "profile") and user.profile.role:
        if is_super_admin_role(user.profile.role):
            return queryset

        return queryset.filter(profile__clinic=user.profile.clinic)

    return queryset.none()