from functools import wraps
from rest_framework.exceptions import PermissionDenied
from restapi.models import RolePermission

CAN_VIEW = "can_view"
CAN_ADD = "can_add"
CAN_EDIT = "can_edit"
CAN_DELETE = "can_delete"
CAN_PRINT = "can_print"

VALID_ACTIONS = [
    CAN_VIEW,
    CAN_ADD,
    CAN_EDIT,
    CAN_DELETE,
    CAN_PRINT
]


def secure_endpoint(module_key, action):

    def decorator(view_func):

        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):

            user = request.user

            # 🔥 DEMO MODE (skip auth)
            if not user or not hasattr(user, "profile"):
                return view_func(self, request, *args, **kwargs)

            # Validate action
            if action not in VALID_ACTIONS:
                raise Exception(f"Invalid permission action: {action}")

            if not user.profile.role:
                raise PermissionDenied("User role not assigned")

            role = user.profile.role

            role_name = (role.name or "").lower().strip()

            # Super Admin → full access
            if role_name == "super admin":
                return view_func(self, request, *args, **kwargs)

            permission = RolePermission.objects.filter(
                role=role,
                module_key=module_key
            ).first()

            if not permission:
                raise PermissionDenied("Permission not found")

            if not getattr(permission, action, False):
                raise PermissionDenied(f"{action} permission denied")

            return view_func(self, request, *args, **kwargs)

        return wrapper

    return decorator