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

        result.setdefault(module, {})

        # ✅ SETTINGS → WITH SUBCATEGORY
        if category.lower() == "settings":

            result[module].setdefault(category, {})

            if not subcategory:
                continue  # skip null

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