from django.urls import path
from .views import (

    # =========================
    # Clinic
    # =========================
    ClinicCreateAPIView,
    ClinicUpdateAPIView,
    GetClinicView,

    # =========================
    # Department / Equipment
    # =========================
    DepartmentEquipmentCreateAPIView,
    DepartmentEquipmentUpdateAPIView,
    EquipmentInactiveAPIView,
    EquipmentSoftDeleteAPIView,
    ActivateEquipmentAPIView,

    # =========================
    # Event
    # =========================
    EventAPIView,
    ClinicEventListAPIView,

    # =========================
    # Task
    # =========================
    TaskCreateAPIView,
    TaskUpdateAPIView,
    TaskGetAPIView,
    TaskGetByEventAPIView,
    TaskGetByClinicAPIView,
    TaskSoftDeleteAPIView,
    SubTaskSoftDeleteAPIView,
    TaskTimerStartAPIView,
    TaskTimerPauseAPIView,
    TaskTimerStopAPIView,

    # =========================
    # Employee / User
    # =========================
    ClinicEmployeesAPIView,
    EmployeeCreateAPIView,
    UserCreateAPIView,

    # =========================
    # Parameters
    # =========================
    ParameterValueCreateAPIView,
    ParameterValueListAPIView,
    SoftDeleteParameterAPIView,

    # =========================
    # Environment
    # =========================
    EnvironmentCreateAPIView,
    EnvironmentUpdateAPIView,
    EnvironmentGetAPIView,
    EnvironmentParameterPatchAPIView,
    EnvironmentParameterValueCreateAPIView,
    EnvironmentParameterValueListAPIView,
    EnvironmentActivateAPIView,
    EnvironmentInactivateAPIView,
    EnvironmentSoftDeleteAPIView,
    EnvironmentParameterSoftDeleteAPIView,
    # =========================
    # Task Events
    # =========================
    TaskEventListAPIView,
    TaskEventCreateAPIView,
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
   
   # Parameter Value Create API View (POST)
   path("parameter-values/", ParameterValueCreateAPIView.as_view(), name="parameter-value-create"),

    # Parameter Value List API View (GET)
   path("parameters/<int:parameter_id>/values/", ParameterValueListAPIView.as_view(), name="parameter-value-list"),

   # Activate Equipment API View (POST)
   path("equipment/<int:equipment_id>/activate/", ActivateEquipmentAPIView.as_view(), name="activate-equipment"),
   

   # Soft delete parameter
   path('parameters/<int:parameter_id>/soft-delete', SoftDeleteParameterAPIView.as_view(), 
        name='parameter-soft-delete'),

    # Get all tasks by event
   path('tasks/event/<int:event_id>', TaskGetByEventAPIView.as_view(), name='task-get-by-event'),
    
    # Task Timer Management
    path(
    "tasks/<int:id>/timer/start",
    TaskTimerStartAPIView.as_view(),
    name="task-timer-start"
),
    
    # Pause Task Timer
    path(
    "tasks/<int:id>/timer/pause",
    TaskTimerPauseAPIView.as_view(),
    name="task-timer-pause"
),
    # Stop Task Timer
    path(
    "tasks/<int:id>/timer/stop",
    TaskTimerStopAPIView.as_view(),
    name="task-timer-stop"
),
    # Get all tasks by clinic
    path(
    "clinics/<int:clinic_id>/tasks/",
    TaskGetByClinicAPIView.as_view(),
    name="task-get-by-clinic"
),
   
 # ==================================================
    # Environment
    # ==================================================
    path(
        "departments/<int:department_id>/environments/",
        EnvironmentCreateAPIView.as_view(),
        name="environment-create"
    ),
    path(
        "environments/<int:environment_id>/",
        EnvironmentUpdateAPIView.as_view(),
        name="environment-update"
    ),
    path(
        "environments/<int:environment_id>/get/",
        EnvironmentGetAPIView.as_view(),
        name="environment-get"
    ),

    # Environment Parameters
    path(
        "environment-parameters/<int:parameter_id>/",
        EnvironmentParameterPatchAPIView.as_view(),
        name="environment-parameter-patch"
    ),

    # Create Environment Parameter Value (POST)
path(
    "environment-parameter-values/",
    EnvironmentParameterValueCreateAPIView.as_view(),
    name="environment-parameter-value-create"
),

# List Environment Parameter Values by parameter_id (GET)
path(
    "environment-parameter-values/<int:value_id>/",
    EnvironmentParameterValueListAPIView.as_view(),
    name="environment-parameter-value-get"
),

# ==================================================
    # Environment active/inactive/delete
    # ==================================================
    path(
        "environments/<int:environment_id>/activate/",
        EnvironmentActivateAPIView.as_view(),
        name="environment-activate"
    ),

    path(
        "environments/<int:environment_id>/inactivate/",
        EnvironmentInactivateAPIView.as_view(),
        name="environment-inactivate"
    ),

    path(
        "environments/<int:environment_id>/delete/",
        EnvironmentSoftDeleteAPIView.as_view(),
        name="environment-soft-delete"
    ),

    # ==================================================
    # Environment Parameter soft delete
    # ==================================================
    path(
        "environment-parameters/<int:parameter_id>/delete/",
        EnvironmentParameterSoftDeleteAPIView.as_view(),
        name="environment-parameter-soft-delete"
    ),

    # ==================================================
    # Task Events
    # ==================================================
    
    path("task-events/", TaskEventListAPIView.as_view(), name="task-event-list"),
    path("task-events/create/", TaskEventCreateAPIView.as_view(), name="task-event-create"),
    path("task-events/<int:task_event_id>/", TaskEventListAPIView.as_view(), name="task-event-get"),

]
