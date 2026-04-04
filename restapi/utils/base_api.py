from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from restapi.utils.tenant import filter_by_clinic


class BaseAPIView(APIView):

    # =========================
    # ✅ GET FILTERED QUERYSET
    # =========================
    def get_queryset(self, queryset):
        return filter_by_clinic(queryset, self.request.user)

    # =========================
    # ✅ OBJECT LEVEL SECURITY
    # =========================
    def check_object_permission(self, obj):
        user = self.request.user

        # Super Admin → allow all
        if (
            hasattr(user, "profile") and
            user.profile.role and
            user.profile.role.name and
            user.profile.role.name.lower().strip() == "super admin"
        ):
            return obj

        # ❌ No profile
        if not hasattr(user, "profile"):
            raise PermissionDenied("User profile not found")

        # ❌ No clinic
        if not user.profile.clinic:
            raise PermissionDenied("Clinic not assigned")

        # ✅ Check object clinic (GENERIC 🔥)
        if hasattr(obj, "clinic"):
            if obj.clinic != user.profile.clinic:
                raise PermissionDenied("Not allowed")

        elif hasattr(obj, "profile"):
            if obj.profile.clinic != user.profile.clinic:
                raise PermissionDenied("Not allowed")

        return obj