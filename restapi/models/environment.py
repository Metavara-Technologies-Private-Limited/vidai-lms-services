from django.db import models
from .department import Department

# =========================
# Environment
# =========================
class Environment(models.Model):
    environment_name = models.CharField(max_length=255)

    # FK → Department
    dep = models.ForeignKey(
        "Department",
        on_delete=models.CASCADE,
        related_name="environments"
    )

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "environment"

    def __str__(self):
        return self.environment_name
    
# =========================
# Environment Parameter
# =========================
class Environment_Parameter(models.Model):
    environment = models.ForeignKey(
        Environment,
        on_delete=models.CASCADE,
        related_name="parameters"
    )

    env_parameter_name = models.CharField(max_length=255)

    # Flexible config (thresholds, units, limits, etc.)
    config = models.JSONField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "environment_parameter"

    def __str__(self):
        return self.env_parameter_name

# =========================
# Environment Parameter Value
# =========================
class Environment_Parameter_Value(models.Model):
    environment_parameter = models.ForeignKey(
        Environment_Parameter,
        on_delete=models.CASCADE,
        related_name="values"
    )

    environment = models.ForeignKey(
        Environment,
        on_delete=models.CASCADE,
        related_name="parameter_values"
    )

    content = models.CharField(max_length=255)
    log_time = models.DateTimeField(null=True, blank=True)

    # ✅ ADD THIS
    is_active = models.BooleanField(default=True)

    #  optional: keep is_deleted ONLY for hard removal
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
