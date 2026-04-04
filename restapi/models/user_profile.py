from django.db import models
from django.contrib.auth.models import User
from .role import Role


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    first_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)

    gender = models.CharField(
        max_length=10,
        choices=[
            ("Male", "Male"),
            ("Female", "Female"),
            ("Other", "Other")
        ],
        null=True,
        blank=True
    )

    date_of_birth = models.DateField(null=True, blank=True)
    date_of_joining = models.DateField(null=True, blank=True)

    mobile_no = models.CharField(max_length=15, null=True, blank=True)

    
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,  
        related_name="users",
        null=True,
        blank=True
    )

    photo = models.ImageField(upload_to="user_profiles/", null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.email