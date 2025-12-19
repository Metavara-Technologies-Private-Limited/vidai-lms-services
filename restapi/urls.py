from django.urls import path
from .views import (
    ClinicCreateAPIView,
    ClinicUpdateAPIView,
    GetClinicView,
    DepartmentEquipmentCreateAPIView,
    DepartmentEquipmentUpdateAPIView,
    EquipmentInactiveAPIView,
    EquipmentSoftDeleteAPIView,
   
)

urlpatterns = [
    # Create Clinic
    path('clinics', ClinicCreateAPIView.as_view(), name='clinic-create'),

    # Update Clinic (PUT)
    path('clinics/<int:clinic_id>/', ClinicUpdateAPIView.as_view(), name='clinic-update'),

    # Get Clinic by ID (GET)
    path('get_clinic/<int:clinic_id>/', GetClinicView.as_view(), name='clinic-get'),

    # Create Equipment under Department
    path(
        'departments/<int:department_id>/equipments/', 
        DepartmentEquipmentCreateAPIView.as_view(), name='department-equipment-create'),

    #Update Equipment under Department
    path(
    "departments/<int:department_id>/equipments/<int:equipment_id>/",
    DepartmentEquipmentUpdateAPIView.as_view(),
    name="department-equipment-update"
),

    # in_active Equipment
    path(
        'departments/<int:department_id>/equipments/<int:equipment_id>/inactive/',
        EquipmentInactiveAPIView.as_view()
    ),
    # soft delete Equipment
    path(
    "departments/<int:department_id>/equipments/<int:equipment_id>/delete/",
    EquipmentSoftDeleteAPIView.as_view(),
),




]
