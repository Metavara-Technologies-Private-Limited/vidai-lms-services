from django.db import models


# =========================
# Clinic
# =========================
class Clinic(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


# =========================
# Department
# =========================
class Department(models.Model):
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# =========================
# Equipments
# =========================
class Equipments(models.Model):
    equipment_name = models.CharField(max_length=200)
    dep = models.ForeignKey(Department, on_delete=models.CASCADE)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.equipment_name


# =========================
# Equipment Details
# =========================
class EquipmentDetails(models.Model):
    equipment = models.ForeignKey(Equipments, on_delete=models.CASCADE)
    equipment_num = models.CharField(max_length=200)
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.equipment_num


# =========================
# Parameters (DEFINITION ONLY)
# content REMOVED
# =========================
class Parameters(models.Model):
    equipment = models.ForeignKey(Equipments, on_delete=models.CASCADE)
    parameter_name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.parameter_name


# =========================
# Parameter Values (NEW TABLE)
# =========================
class ParameterValues(models.Model):
    parameter = models.ForeignKey(
        Parameters,
        on_delete=models.CASCADE,
        related_name="parameter_values"
    )
    content = models.JSONField()
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
