from django.db import models
from .role import Role


class RolePermission(models.Model):

    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="permissions"   # ✅ IMPORTANT
    )

    module_key = models.CharField(max_length=100)
    category_key = models.CharField(max_length=100)
    subcategory_key = models.CharField(max_length=100, null=True, blank=True)

    can_view = models.BooleanField(default=False)
    can_add = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_print = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)   # ✅ optional but useful

    class Meta:
        # ✅ Prevent duplicate permissions
        unique_together = (
            "role",
            "module_key",
            "category_key",
            "subcategory_key",
        )

        # ✅ Performance optimization
        indexes = [
            models.Index(fields=["module_key"]),
            models.Index(fields=["category_key"]),
        ]

    def __str__(self):
        return f"{self.role.name} - {self.module_key}"