from restapi.models import RolePermission


def get_user_permissions(user):

    if not hasattr(user, "profile") or not user.profile.role:
        return {}

    role = user.profile.role

    permissions = RolePermission.objects.select_related("role").filter(
        role=role,
        
    )

    result = {}

    for perm in permissions:
        module = perm.module_key
        category = perm.category_key

        result.setdefault(module, {})
        result[module].setdefault(category, [])

        result[module][category].append({
            "subcategory": perm.subcategory_key,
            "can_view": perm.can_view,
            "can_add": perm.can_add,
            "can_edit": perm.can_edit,
            "can_print": perm.can_print,
        })

    return result