from django.contrib import admin
from .models import Clinic, Department, Equipments, EquipmentDetails, Parameters

admin.site.register(Clinic)
admin.site.register(Department)
admin.site.register(Equipments)
admin.site.register(EquipmentDetails)
admin.site.register(Parameters)
