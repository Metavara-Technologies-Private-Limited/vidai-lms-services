from django.db import models


class Clinic(models.Model):
    #id = models.IntegerField(primary_key=True)   # MANUAL INTEGER PRIMARY KEY
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class Department(models.Model):
    #id = models.IntegerField(primary_key=True)   # MANUAL INTEGER PRIMARY KEY
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Equipments(models.Model):
    #id = models.IntegerField(primary_key=True)   # MANUAL INTEGER PRIMARY KEY
    equipment_name = models.CharField(max_length=200)
    dep = models.ForeignKey(Department, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.equipment_name


class EquipmentDetails(models.Model):
    #id = models.IntegerField(primary_key=True)   # MANUAL INTEGER PRIMARY KEY
    equipment_num = models.CharField(max_length=200)
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    equipment = models.ForeignKey(Equipments, on_delete=models.CASCADE)

    def __str__(self):
        return self.equipment_num


class Parameters(models.Model):
    #id = models.IntegerField(primary_key=True)   # MANUAL INTEGER PRIMARY KEY
    parameter_name = models.CharField(max_length=200)
    equipment = models.ForeignKey(Equipments, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    content = models.JSONField()                 # Stored as JSONB in PostgreSQL
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.parameter_name
