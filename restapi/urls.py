from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .views import (
    ClinicCreateAPIView,
    ClinicUpdateAPIView,
    GetClinicView,
    DepartmentEquipmentCreateAPIView,
    DepartmentEquipmentUpdateAPIView,
    EquipmentInactiveAPIView,TaskGetAPIView, TaskSoftDeleteAPIView, SubTaskSoftDeleteAPIView,
    EquipmentSoftDeleteAPIView,
    EventAPIView, UserCreateAPIView,
    ClinicEventListAPIView, ClinicEmployeesAPIView, EmployeeCreateAPIView,
    TaskCreateAPIView, TaskUpdateAPIView
   
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
    path("departments/<int:department_id>/equipments/<int:equipment_id>/delete/", EquipmentSoftDeleteAPIView.as_view(),),

    # Event API View
    path('event', EventAPIView.as_view(), name='event-create'),

    # Get Events by Clinic ID
    path("clinics/<int:clinic_id>/event/",ClinicEventListAPIView.as_view(), name="clinic-events"),

    # Task API View(POST)
    path('tasks', TaskCreateAPIView.as_view(), name='task-create'),

    # Update Task (PUT)
    path('tasks/<int:task_id>',TaskUpdateAPIView.as_view(), name='task-update'),

    # Employee Create API View (POST)
    path("employees/", EmployeeCreateAPIView.as_view(), name="employee-create"),

    # Get Task by ID
    path("tasks/<int:task_id>/", TaskGetAPIView.as_view(), name="task-get"),

    # Soft delete task
    path("tasks/<int:task_id>/delete/", TaskSoftDeleteAPIView.as_view(),name="task-soft-delete"),

    # (Optional) Soft delete subtask
    path("subtasks/<int:subtask_id>/delete/", SubTaskSoftDeleteAPIView.as_view(), name="subtask-soft-delete"),


    # Clinic Employees API View (GET)
    path("clinics/<int:clinic_id>/employees/", ClinicEmployeesAPIView.as_view(), name="clinic-employees"),

    # User Create API View (POST)
    path("users/", UserCreateAPIView.as_view(), name="user-create"),

    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),


]
