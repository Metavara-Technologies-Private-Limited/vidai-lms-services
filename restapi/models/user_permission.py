from django.db import models
from django.contrib.auth.models import User


class UserPermission(models.Model):
    """
    Individual user-level permission override.
    When a user has records here, these take precedence over their role's permissions.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="individual_permissions",
    )

    module_key = models.CharField(max_length=100)
    category_key = models.CharField(max_length=100)
    subcategory_key = models.CharField(max_length=100, null=True, blank=True)

    can_view = models.BooleanField(default=False)
    can_add = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_print = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "module_key", "category_key", "subcategory_key")

        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["module_key"]),
            models.Index(fields=["category_key"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.module_key}/{self.category_key}"
