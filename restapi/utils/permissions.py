from restapi.models import RolePermission


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

        # Initialize module
        if module not in result:
            result[module] = {}

        # 🔥 SPECIAL CASE: SETTINGS ONLY
        if module == "Settings":

            if category not in result[module]:
                result[module][category] = {}

            sub_key = subcategory or "General"

            if sub_key not in result[module][category]:
                result[module][category][sub_key] = []

            result[module][category][sub_key].append({
                "can_view": perm.can_view,
                "can_add": perm.can_add,
                "can_edit": perm.can_edit,
                "can_print": perm.can_print,
            })

        # 🔥 ALL OTHER MODULES (NO SUBCATEGORY)
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