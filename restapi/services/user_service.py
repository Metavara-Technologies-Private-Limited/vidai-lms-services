from restapi.models import RolePermission
from restapi.utils.permissions import is_super_admin_role, get_user_role

# 🔥 IMPORTANT
from restapi.utils.clinic_context import resolve_request_clinic


# =========================
# ✅ GET USER PERMISSIONS
# =========================
def get_user_permissions(user):

    if not hasattr(user, "profile") or not user.profile.role:
        return {}

    role = user.profile.role

    # ✅ Permissions are role-based (no clinic dependency)
    permissions = RolePermission.objects.filter(role=role)

    result = {}

    for perm in permissions:
        module = perm.module_key
        category = perm.category_key
        subcategory = perm.subcategory_key

        result.setdefault(module, {})

        # ✅ SETTINGS → WITH SUBCATEGORY
        if category and category.lower() == "settings":

            result[module].setdefault(category, {})

            if not subcategory:
                continue

            result[module][category].setdefault(subcategory, [])

            result[module][category][subcategory].append({
                "can_view": perm.can_view,
                "can_add": perm.can_add,
                "can_edit": perm.can_edit,
                "can_print": perm.can_print,
            })

        # ✅ OTHER MODULES → NO SUBCATEGORY
        else:

            result[module].setdefault(category, [])

            result[module][category].append({
                "can_view": perm.can_view,
                "can_add": perm.can_add,
                "can_edit": perm.can_edit,
                "can_print": perm.can_print,
            })

    return result


# =========================
# ✅ FINAL CLINIC FILTER FUNCTION (FIXED)
# =========================
def filter_by_clinic(queryset, request):
    """
    FINAL BEHAVIOR:
    - ALL roles (Super Admin / Admin / User)
    - Data strictly based on selected clinic (dropdown)
    - No dependency on user.profile.clinic
    """

    try:
        clinic = resolve_request_clinic(request)  # 🔥 CORE FIX
    except Exception:
        return queryset.none()

    # =========================
    # HANDLE USER QUERYSET
    # =========================
    if queryset.model.__name__ == "User":
        return queryset.filter(profile__clinic=clinic)

    # =========================
    # HANDLE PROFILE QUERYSET
    # =========================
    if queryset.model.__name__ == "UserProfile":
        return queryset.filter(clinic=clinic)

    # =========================
    # HANDLE GENERIC MODELS (Lead, Campaign, etc.)
    # =========================
    if hasattr(queryset.model, "clinic"):
        return queryset.filter(clinic=clinic)

    # =========================
    # FALLBACK
    # =========================
    return queryset.none()