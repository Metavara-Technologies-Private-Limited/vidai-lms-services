from rest_framework import serializers
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

from restapi.models.user_profile import UserProfile
from restapi.models.role import Role
from restapi.utils.permissions import (
    get_user_permissions,
    has_permission,
    has_subcategory_permission,
    is_super_admin_role,
)


def _resolve_default_role(request):
    user_role = Role.objects.filter(name__iexact="User").first()
    if user_role:
        return user_role

    if request and hasattr(request, "user") and hasattr(request.user, "profile"):
        if request.user.profile and request.user.profile.role:
            return request.user.profile.role

    return Role.objects.filter(is_active=True).first() or Role.objects.first()


def _validate_profile_photo(file_obj):
    if not file_obj:
        return

    max_size = int(
        getattr(settings, "MAX_PROFILE_PHOTO_UPLOAD_BYTES", 20 * 1024 * 1024)
    )
    file_size = getattr(file_obj, "size", 0) or 0
    if file_size > max_size:
        raise serializers.ValidationError(
            {"photo": f"Profile photo must be {max_size // (1024 * 1024)}MB or smaller"}
        )

    content_type = getattr(file_obj, "content_type", "") or ""
    if content_type and not content_type.lower().startswith("image/"):
        raise serializers.ValidationError({"photo": "Only image files are allowed"})


class UserSerializer(serializers.ModelSerializer):

    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    password = serializers.CharField(write_only=True, required=False)
    confirm_password = serializers.CharField(write_only=True, required=False)

    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    gender = serializers.CharField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False)
    date_of_joining = serializers.DateField(required=False)
    mobile_no = serializers.CharField(required=False)

    role = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        required=False
    )

    photo = serializers.ImageField(required=False)
    remove_photo = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "password",
            "confirm_password",
            "first_name",
            "last_name",
            "gender",
            "date_of_birth",
            "date_of_joining",
            "mobile_no",
            "role",
            "photo",
            "remove_photo"
        ]

    # =========================
    # VALIDATION
    # =========================
    def validate(self, data):

        request = self.context.get("request")

        password = data.get("password")
        confirm_password = data.get("confirm_password")
        email = data.get("email")
        role = data.get("role")
        photo = data.get("photo")

        if photo is not None:
            _validate_profile_photo(photo)

        if not self.instance:
            if not email:
                raise serializers.ValidationError({"email": "Email is required"})
            if not password:
                raise serializers.ValidationError({"password": "Password is required"})
            if not confirm_password:
                raise serializers.ValidationError({"confirm_password": "Confirm password is required"})
            if not role:
                raise serializers.ValidationError({"role": "Role is required"})
            if password != confirm_password:
                raise serializers.ValidationError({"password": "Passwords do not match"})

        if self.instance is None:
            if email and User.objects.filter(email=email).exists():
                raise serializers.ValidationError({"email": "Email already exists"})
        else:
            if email and User.objects.exclude(id=self.instance.id).filter(email=email).exists():
                raise serializers.ValidationError({"email": "Email already exists"})

        username = data.get("username")
        if username:
            if self.instance:
                if User.objects.exclude(id=self.instance.id).filter(username=username).exists():
                    raise serializers.ValidationError({"username": "Username already exists"})
            else:
                if User.objects.filter(username=username).exists():
                    raise serializers.ValidationError({"username": "Username already exists"})

        if "role" in data and data.get("role") is not None:
            if not request or not hasattr(request.user, "profile"):
                raise serializers.ValidationError("Login required to assign role")

            if not is_super_admin_role(request.user.profile.role):
                raise serializers.ValidationError("Only Super Admin can assign roles")

        return data

    # =========================
    # CREATE USER
    # =========================
    def create(self, validated_data):
        validated_data.pop("remove_photo", False)

        profile_data = {
            "first_name": validated_data.pop("first_name", None),
            "last_name": validated_data.pop("last_name", None),
            "gender": validated_data.pop("gender", None),
            "date_of_birth": validated_data.pop("date_of_birth", None),
            "date_of_joining": validated_data.pop("date_of_joining", None),
            "mobile_no": validated_data.pop("mobile_no", None),
            "photo": validated_data.pop("photo", None),
        }

        role = validated_data.pop("role", None)
        request = self.context.get("request")

        if not role:
            role = _resolve_default_role(request)

        if not role:
            raise serializers.ValidationError("No role configured. Please create a role first")

        profile_data["role"] = role

        if request and hasattr(request.user, "profile"):
            profile_data["clinic"] = request.user.profile.clinic

        password = validated_data.pop("password", None)
        validated_data.pop("confirm_password", None)

        username = validated_data.pop("username", None)

        user = User.objects.create_user(
            username=username or validated_data["email"],
            email=validated_data["email"],
            password=password
        )

        profile, _ = UserProfile.objects.update_or_create(
            user=user,
            defaults=profile_data
        )

        user.refresh_from_db()

        return user

    # =========================
    # UPDATE USER
    # =========================
    def update(self, instance, validated_data):

        profile, _ = UserProfile.objects.get_or_create(user=instance)
        remove_photo = validated_data.pop("remove_photo", False)

        if "email" in validated_data:
            instance.email = validated_data["email"]

        if "username" in validated_data:
            instance.username = validated_data["username"]

        password = validated_data.get("password")
        if password:
            instance.set_password(password)

        instance.save()

        for field in [
            "first_name",
            "last_name",
            "gender",
            "date_of_birth",
            "date_of_joining",
            "mobile_no"
        ]:
            if field in validated_data:
                setattr(profile, field, validated_data[field])

        if "role" in validated_data:
            profile.role = validated_data["role"]

        if remove_photo:
            if profile.photo:
                profile.photo.delete(save=False)
            profile.photo = None

        if "photo" in validated_data:
            if profile.photo:
                profile.photo.delete(save=False)
            profile.photo = validated_data.get("photo")

        profile.save()

        return instance

    # =========================
    # RESPONSE FORMAT
    # =========================
    def to_representation(self, instance):

        try:
            profile = instance.profile
        except ObjectDoesNotExist:
            profile = None

        permissions = {}
        if profile and profile.role:
            permissions = get_user_permissions(instance)

        data = {
            "id": instance.id,
            "username": instance.username,
            "email": instance.email,
            "first_name": profile.first_name if profile else "",
            "last_name": profile.last_name if profile else "",
            "gender": profile.gender if profile else "",
            "date_of_birth": profile.date_of_birth if profile else None,
            "date_of_joining": profile.date_of_joining if profile else None,
            "mobile_no": profile.mobile_no if profile else "",
            "role": {
                "id": profile.role.id if profile and profile.role else None,
                "name": profile.role.name if profile and profile.role else None
            },
            "clinic": {
                "id": profile.clinic.id if profile and profile.clinic else None,
                "name": profile.clinic.name if profile and profile.clinic else None
            },
            "photo": photo_url,
            "is_active": profile.is_active if profile else False,
            "permissions": permissions
        }

        if not request:
            return data

        user = getattr(request, "user", None)
        if not user or not hasattr(user, "profile") or not getattr(user, "profile", None):
            return data

        if getattr(user, "id", None) == instance.id:
            return data

        if is_super_admin_role(user.profile.role):
            return data

        can_view_users = (
            has_permission(user, "user_management", "users", "view")
            or has_subcategory_permission(user, "settings", "settings", "users", "view")
            or has_subcategory_permission(user, "settings", "settings", "user", "view")
        )

        if not can_view_users:
            return {}

        # View permission already validated above. Keep a consistent shape so
        # edit forms can render all fields (including profile photo).
        return data
