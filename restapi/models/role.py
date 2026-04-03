from django.db import models


class Role(models.Model):

    name = models.CharField(max_length=50, unique=True)

    is_active = models.BooleanField(default=True)   # ✅ keep this

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # ✅ useful later

    def __str__(self):
        return self.name