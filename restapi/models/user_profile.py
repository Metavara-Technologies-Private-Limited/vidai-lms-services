import os
import uuid

from django.db import models
from django.contrib.auth.models import User
from .role import Role
from .clinic import Clinic


def user_profile_photo_upload_to(instance, filename):
    _, ext = os.path.splitext(filename or "")
    normalized_ext = ext.lower() or ".jpg"
    user_id = getattr(instance, "user_id", None) or "pending"
    return f"user_profiles/user_{user_id}/{uuid.uuid4().hex}{normalized_ext}"


class UserProfile(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    first_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)

    gender = models.CharField(max_length=10, null=True, blank=True)

    date_of_birth = models.DateField(null=True, blank=True)
    date_of_joining = models.DateField(null=True, blank=True)

    mobile_no = models.CharField(max_length=15, null=True, blank=True)

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users"
    )

    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # ✅ NEW FIELD
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_users"
    )

    photo = models.ImageField(
        upload_to=user_profile_photo_upload_to,
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.email
