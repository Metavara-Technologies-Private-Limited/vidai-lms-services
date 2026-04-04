from functools import wraps
from rest_framework.exceptions import PermissionDenied
from restapi.models import RolePermission


def has_permission(module_key, action):
    """
    action: can_view / can_add / can_edit / can_print
    """

    def decorator(view_func):

        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):

            user = request.user

            # Check role
            if not hasattr(user, "profile") or not user.profile.role:
                raise PermissionDenied("User role not assigned")

            role = user.profile.role

            # Fetch permission
            permission = RolePermission.objects.filter(
                role=role,
                module_key=module_key,
                is_active=True
            ).first()

            if not permission:
                raise PermissionDenied("Permission not found")

            # Check access
            if not getattr(permission, action, False):
                raise PermissionDenied(f"{action} permission denied")

            return view_func(self, request, *args, **kwargs)

        return wrapper

    return decorator