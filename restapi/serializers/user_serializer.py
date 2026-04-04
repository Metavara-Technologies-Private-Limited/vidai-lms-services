from rest_framework import serializers
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

from restapi.models.user_profile import UserProfile
from restapi.models.role import Role
from restapi.services.user_service import get_user_permissions


class UserSerializer(serializers.ModelSerializer):

    # =========================
    # 🔹 USER FIELDS
    # =========================
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    password = serializers.CharField(write_only=True, required=False)
    confirm_password = serializers.CharField(write_only=True, required=False)

    # =========================
    # 🔹 PROFILE FIELDS
    # =========================
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
            "photo"
        ]

    # =========================
    # ✅ VALIDATION
    # =========================
    def validate(self, data):

        request = self.context.get("request")

        # 🔹 PASSWORD VALIDATION
        if not self.instance:
            if not data.get("password"):
                raise serializers.ValidationError("Password is required")

        password = data.get("password")
        confirm_password = data.get("confirm_password")

        if password or confirm_password:
            if not password or not confirm_password:
                raise serializers.ValidationError(
                    "Both password and confirm password are required"
                )
            if password != confirm_password:
                raise serializers.ValidationError("Passwords do not match")

        # 🔹 EMAIL VALIDATION
        email = data.get("email")

        if self.instance is None:
            if not email:
                raise serializers.ValidationError("Email is required")

            if User.objects.filter(email=email).exists():
                raise serializers.ValidationError("Email already exists")
        else:
            if email and User.objects.exclude(id=self.instance.id).filter(email=email).exists():
                raise serializers.ValidationError("Email already exists")

        # 🔹 USERNAME VALIDATION
        username = data.get("username")
        if username:
            if self.instance:
                if User.objects.exclude(id=self.instance.id).filter(username=username).exists():
                    raise serializers.ValidationError("Username already exists")
            else:
                if User.objects.filter(username=username).exists():
                    raise serializers.ValidationError("Username already exists")

        # 🔥 ROLE SECURITY (STRICT)
        if "role" in data:
            if not request or not hasattr(request.user, "profile"):
                raise serializers.ValidationError("Login required to assign role")

            current_role = request.user.profile.role

            if not current_role or current_role.name.lower() != "super admin":
                raise serializers.ValidationError(
                    "Only Super Admin can assign roles"
                )

        return data

    # =========================
    # ✅ CREATE USER
    # =========================
    def create(self, validated_data):

        # 🔹 Extract profile fields
        profile_data = {
            "first_name": validated_data.pop("first_name", None),
            "last_name": validated_data.pop("last_name", None),
            "gender": validated_data.pop("gender", None),
            "date_of_birth": validated_data.pop("date_of_birth", None),
            "date_of_joining": validated_data.pop("date_of_joining", None),
            "mobile_no": validated_data.pop("mobile_no", None),
            "photo": validated_data.pop("photo", None),
        }

        # 🔥 ROLE HANDLING (FIXED — NO SILENT OVERRIDE)
        role = validated_data.pop("role", None)

        if not role:
            raise serializers.ValidationError("Role is required")

        profile_data["role"] = role

        # 🔹 USER CREATE
        password = validated_data.pop("password", None)
        validated_data.pop("confirm_password", None)

        username = validated_data.pop("username", None)

        user = User.objects.create_user(
            username=username or validated_data["email"],
            email=validated_data["email"],
            password=password
        )

        # 🔹 PROFILE CREATE
        UserProfile.objects.update_or_create(
            user=user,
            defaults=profile_data
        )

        return user

    # =========================
    # ✅ UPDATE USER
    # =========================
    def update(self, instance, validated_data):

        profile = instance.profile

        # 🔹 USER UPDATE
        if "email" in validated_data:
            instance.email = validated_data["email"]

        instance.username = validated_data.get("username", instance.username)

        password = validated_data.get("password")
        if password:
            instance.set_password(password)

        instance.save()

        # 🔹 PROFILE UPDATE
        for field in [
            "first_name",
            "last_name",
            "gender",
            "date_of_birth",
            "date_of_joining",
            "mobile_no"
        ]:
            if field in validated_data:
                setattr(profile, field, validated_data.get(field))

        # 🔹 ROLE UPDATE
        if "role" in validated_data:
            profile.role = validated_data.get("role")

        # 🔹 PHOTO UPDATE
        if "photo" in validated_data:
            new_photo = validated_data.get("photo")

            if new_photo is None:
                if profile.photo:
                    profile.photo.delete(save=False)
                profile.photo = None
            else:
                if profile.photo:
                    profile.photo.delete(save=False)
                profile.photo = new_photo

        profile.save()

        return instance

    # =========================
    # ✅ RESPONSE FORMAT
    # =========================
    def to_representation(self, instance):

        try:
            profile = instance.profile
        except ObjectDoesNotExist:
            profile = None

        permissions = {}
        if profile and profile.role:
            permissions = get_user_permissions(instance)

        return {
            "id": instance.id,
            "username": instance.username,
            "email": instance.email,

            "first_name": profile.first_name if profile and profile.first_name else "",
            "last_name": profile.last_name if profile and profile.last_name else "",
            "gender": profile.gender if profile and profile.gender else "",
            "date_of_birth": profile.date_of_birth if profile else None,
            "date_of_joining": profile.date_of_joining if profile else None,
            "mobile_no": profile.mobile_no if profile and profile.mobile_no else "",

            "role": {
                "id": profile.role.id if profile and profile.role else None,
                "name": profile.role.name if profile and profile.role else None
            },

            "photo": profile.photo.url if profile and profile.photo else None,
            "is_active": profile.is_active if profile else False,

            "permissions": permissions
        }