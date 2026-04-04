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
    email = serializers.EmailField(required=True)
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
    role = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all(), required=False)
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

        #  REQUIRE PASSWORD ON CREATE
        if not self.instance and not data.get("password"):
            raise serializers.ValidationError("Password is required")

        password = data.get("password")
        confirm_password = data.get("confirm_password")

        #  PASSWORD VALIDATION (CREATE + UPDATE)
        if password or confirm_password:
            if not password or not confirm_password:
                raise serializers.ValidationError(
                    "Both password and confirm password are required"
                )

            if password != confirm_password:
                raise serializers.ValidationError("Passwords do not match")

        #  EMAIL REQUIRED
        email = data.get("email")
        if not email:
            raise serializers.ValidationError("Email is required")

        #  EMAIL UNIQUE
        if self.instance:
            if User.objects.exclude(id=self.instance.id).filter(email=email).exists():
                raise serializers.ValidationError("Email already exists")
        else:
            if User.objects.filter(email=email).exists():
                raise serializers.ValidationError("Email already exists")

        #  USERNAME UNIQUE
        username = data.get("username")
        if username:
            if self.instance:
                if User.objects.exclude(id=self.instance.id).filter(username=username).exists():
                    raise serializers.ValidationError("Username already exists")
            else:
                if User.objects.filter(username=username).exists():
                    raise serializers.ValidationError("Username already exists")

        #  ROLE SECURITY (ONLY SUPER ADMIN)
        request = self.context.get("request")
        if request and hasattr(request.user, "profile"):
            current_role = request.user.profile.role

            if current_role and current_role.name.lower() != "super admin":
                if "role" in data:
                    raise serializers.ValidationError("You cannot assign roles")

        return data

    # =========================
    # ✅ CREATE USER
    # =========================
    def create(self, validated_data):

        profile_data = {
            "first_name": validated_data.pop("first_name", None),
            "last_name": validated_data.pop("last_name", None),
            "gender": validated_data.pop("gender", None),
            "date_of_birth": validated_data.pop("date_of_birth", None),
            "date_of_joining": validated_data.pop("date_of_joining", None),
            "mobile_no": validated_data.pop("mobile_no", None),
            "photo": validated_data.pop("photo", None),
        }

        #  DEFAULT ROLE
        role = validated_data.pop("role", None)
        if not role:
            role = Role.objects.filter(name="User").first()
            if not role:
                raise serializers.ValidationError("Default role 'User' not found")

        profile_data["role"] = role

        password = validated_data.pop("password", None)
        validated_data.pop("confirm_password", None)

        username = validated_data.pop("username", None)

        user = User.objects.create_user(
            username=username or validated_data["email"],
            email=validated_data["email"],
            password=password
        )

        UserProfile.objects.create(user=user, **profile_data)

        return user

    # =========================
    # ✅ UPDATE USER
    # =========================
    def update(self, instance, validated_data):
        profile = instance.profile

        #  EMAIL UPDATE (FIXED)
        if "email" in validated_data:
            instance.email = validated_data["email"]

        #  USERNAME UPDATE
        instance.username = validated_data.get("username", instance.username)

        #  PASSWORD UPDATE
        password = validated_data.get("password")
        if password:
            instance.set_password(password)

        instance.save()

        #  PROFILE UPDATE
        profile.first_name = validated_data.get("first_name", profile.first_name)
        profile.last_name = validated_data.get("last_name", profile.last_name)
        profile.gender = validated_data.get("gender", profile.gender)
        profile.date_of_birth = validated_data.get("date_of_birth", profile.date_of_birth)
        profile.date_of_joining = validated_data.get("date_of_joining", profile.date_of_joining)
        profile.mobile_no = validated_data.get("mobile_no", profile.mobile_no)

        #  ROLE UPDATE
        if "role" in validated_data:
            profile.role = validated_data.get("role")

        #  PHOTO HANDLE
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

            "photo": profile.photo.url if profile and profile.photo else None,
            "is_active": profile.is_active if profile else False,

            #  DYNAMIC PERMISSIONS
            "permissions": permissions
        }