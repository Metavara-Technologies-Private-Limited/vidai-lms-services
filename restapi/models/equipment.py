from django.db import models
from .department import Department

class Equipments(models.Model):
    equipment_name = models.CharField(max_length=200)
    dep = models.ForeignKey(Department, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.equipment_name


class EquipmentDetails(models.Model):
    equipment = models.ForeignKey(Equipments, on_delete=models.CASCADE)
    equipment_num = models.CharField(max_length=200)
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
