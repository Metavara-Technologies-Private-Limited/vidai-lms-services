from restapi.models import RolePermission
from restapi.utils.permissions import is_super_admin_role, get_user_role


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

        result.setdefault(module, {})

        # ✅ SETTINGS → WITH SUBCATEGORY
        if category.lower() == "settings":

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
# ✅ FINAL CLINIC FILTER FUNCTION
# =========================
def filter_by_clinic(queryset, request):
    """
    Multi-clinic behavior:
    - Super Admin → sees users of selected clinic
    - Normal users → sees only their clinic users
    """

    user = request.user

    if not user or not hasattr(user, "profile") or not user.profile:
        return queryset.none()

    role = get_user_role(user)

    clinic_id = request.query_params.get("clinic_id")

    # =====================================
    # ✅ SUPER ADMIN
    # =====================================
    if is_super_admin_role(role):

        if clinic_id and str(clinic_id).isdigit():
            return queryset.filter(profile__clinic_id=int(clinic_id))

        if user.profile.clinic_id:
            return queryset.filter(profile__clinic_id=user.profile.clinic_id)

        return queryset.none()

    # =====================================
    # ✅ NORMAL USERS
    # =====================================
    if user.profile.clinic_id:
        return queryset.filter(profile__clinic_id=user.profile.clinic_id)

    return queryset.none()