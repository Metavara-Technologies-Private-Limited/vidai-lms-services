from rest_framework import serializers
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from restapi.models.user_profile import UserProfile
from restapi.models.role import Role


class UserSerializer(serializers.ModelSerializer):

    # 🔹 USER FIELDS
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=False)
    confirm_password = serializers.CharField(write_only=True, required=False)

    # 🔹 PROFILE FIELDS
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
        password = data.get("password")
        confirm_password = data.get("confirm_password")

        # Password match check
        if password or confirm_password:
            if password != confirm_password:
                raise serializers.ValidationError("Passwords do not match")

        # Email uniqueness
        email = data.get("email")
        if self.instance:
            if User.objects.exclude(id=self.instance.id).filter(email=email).exists():
                raise serializers.ValidationError("Email already exists")
        else:
            if User.objects.filter(email=email).exists():
                raise serializers.ValidationError("Email already exists")

        username = data.get("username")
        if username:
            if self.instance:
                if User.objects.exclude(id=self.instance.id).filter(username=username).exists():
                    raise serializers.ValidationError("Username already exists")
            else:
                if User.objects.filter(username=username).exists():
                    raise serializers.ValidationError("Username already exists")

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
            "role": validated_data.pop("role", None),
            "photo": validated_data.pop("photo", None),
        }

        password = validated_data.pop("password", None)
        validated_data.pop("confirm_password", None)

        username = validated_data.pop("username", None)

        # Create User
        user = User.objects.create_user(
            username=username or validated_data["email"],
            email=validated_data["email"],
            password=password
        )

        # Create Profile
        UserProfile.objects.create(user=user, **profile_data)

        return user

    # =========================
    # ✅ UPDATE USER (WITH PHOTO LOGIC)
    # =========================
    def update(self, instance, validated_data):
        profile = instance.profile

        # Update User
        instance.email = validated_data.get("email", instance.email)
        instance.username = validated_data.get("username", instance.username)

        password = validated_data.get("password")
        if password:
            instance.set_password(password)

        instance.save()

        # Update Profile fields
        profile.first_name = validated_data.get("first_name", profile.first_name)
        profile.last_name = validated_data.get("last_name", profile.last_name)
        profile.gender = validated_data.get("gender", profile.gender)
        profile.date_of_birth = validated_data.get("date_of_birth", profile.date_of_birth)
        profile.date_of_joining = validated_data.get("date_of_joining", profile.date_of_joining)
        profile.mobile_no = validated_data.get("mobile_no", profile.mobile_no)
        profile.role = validated_data.get("role", profile.role)

        # 🔥 PHOTO HANDLE (UPDATE / DELETE / REPLACE)
        if "photo" in validated_data:
            new_photo = validated_data.get("photo")

            # DELETE
            if new_photo is None:
                if profile.photo:
                    profile.photo.delete(save=False)
                profile.photo = None

            # UPDATE / REPLACE
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
            "role": profile.role.id if profile and profile.role else None,
            "photo": profile.photo.url if profile and profile.photo else None,
            "is_active": profile.is_active if profile else False,
        }