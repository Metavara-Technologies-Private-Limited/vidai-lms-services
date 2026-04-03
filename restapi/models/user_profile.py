# restapi/models/user_profile.py

from django.db import models
from django.contrib.auth.models import User
from .role import Role


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    mobile_no = models.CharField(max_length=15, null=True, blank=True)
    designation = models.CharField(max_length=100, null=True, blank=True)

    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="users",   # ✅ FIXED
        null=True,
        blank=True
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)