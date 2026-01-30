from django.urls import path

from .views import (

    # =========================
    # Clinic
    # =========================
    ClinicCreateAPIView,
    ClinicDepartmentsAPIView,
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
    ActivateParameterAPIView,
    InactivateParameterAPIView,
    SoftDeleteParameterAPIView,

    # =========================
    # Environment
    # =========================
    EnvironmentCreateAPIView,
    EnvironmentUpdateAPIView,
    EnvironmentGetAPIView,
    EnvironmentFullHierarchyAPIView,
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

# ==================================================
# Clinic APIs
# ==================================================

    # Create Clinic (POST)
    path("clinics", ClinicCreateAPIView.as_view(), name="clinic-create"),

    # Update Clinic by ID (PUT)
    path("clinics/<int:clinic_id>/", ClinicUpdateAPIView.as_view(), name="clinic-update"),

    # Get Clinic by ID (GET)
    path("get_clinic/<int:clinic_id>/", GetClinicView.as_view(), name="clinic-get"),

    # Get all Departments & Equipments under a Clinic (GET)
    path(
        "clinics/<int:clinic_id>/departments/",
        ClinicDepartmentsAPIView.as_view(),
        name="clinic-departments"
    ),

# ==================================================
# Department / Equipment APIs
# ==================================================

    # Create Equipment under a Department (POST)
    path(
        "departments/<int:department_id>/equipments/",
        DepartmentEquipmentCreateAPIView.as_view(),
        name="department-equipment-create"
    ),

    # Update Equipment under a Department (PUT)
    path(
        "departments/<int:department_id>/equipments/<int:equipment_id>/",
        DepartmentEquipmentUpdateAPIView.as_view(),
        name="department-equipment-update"
    ),

    # Inactivate Equipment (PATCH)
    path(
        "departments/<int:department_id>/equipments/<int:equipment_id>/inactive/",
        EquipmentInactiveAPIView.as_view()
    ),

    # Soft Delete Equipment (PATCH)
    path(
        "departments/<int:department_id>/equipments/<int:equipment_id>/delete/",
        EquipmentSoftDeleteAPIView.as_view()
    ),

    # Activate Equipment (POST)
    path(
        "equipment/<int:equipment_id>/activate/",
        ActivateEquipmentAPIView.as_view(),
        name="activate-equipment"
    ),

# ==================================================
# Event APIs
# ==================================================

    # Create Event (POST)
    path("event", EventAPIView.as_view(), name="event-create"),

    # Get all Events under a Clinic (GET)
    path(
        "clinics/<int:clinic_id>/event/",
        ClinicEventListAPIView.as_view(),
        name="clinic-events"
    ),

# ==================================================
# Task APIs
# ==================================================

    # Create Task (POST)
    path("tasks", TaskCreateAPIView.as_view(), name="task-create"),

    # Update Task by ID (PUT)
    path("tasks/<int:task_id>", TaskUpdateAPIView.as_view(), name="task-update"),

    # Get Task by ID (GET)
    path("tasks/<int:task_id>/", TaskGetAPIView.as_view(), name="task-get"),

    # Soft Delete Task (PATCH)
    path(
        "tasks/<int:task_id>/delete/",
        TaskSoftDeleteAPIView.as_view(),
        name="task-soft-delete"
    ),

    # Get Tasks by Event ID (GET)
    path(
        "tasks/event/<int:event_id>",
        TaskGetByEventAPIView.as_view(),
        name="task-get-by-event"
    ),

    # Get Tasks by Clinic ID (GET)
    path(
        "clinics/<int:clinic_id>/tasks/",
        TaskGetByClinicAPIView.as_view(),
        name="task-get-by-clinic"
    ),

# ==================================================
# Sub Task APIs
# ==================================================

    # Soft Delete Subtask (PATCH)
    path(
        "subtasks/<int:subtask_id>/delete/",
        SubTaskSoftDeleteAPIView.as_view(),
        name="subtask-soft-delete"
    ),

# ==================================================
# Task Timer APIs
# ==================================================

    # Start Task Timer (POST)
    path(
        "tasks/<int:id>/timer/start",
        TaskTimerStartAPIView.as_view(),
        name="task-timer-start"
    ),

    # Pause Task Timer (POST)
    path(
        "tasks/<int:id>/timer/pause",
        TaskTimerPauseAPIView.as_view(),
        name="task-timer-pause"
    ),

    # Stop Task Timer (POST)
    path(
        "tasks/<int:id>/timer/stop",
        TaskTimerStopAPIView.as_view(),
        name="task-timer-stop"
    ),

# ==================================================
# Employee / User APIs
# ==================================================

    # Get Employees under a Clinic (GET)
    path(
        "clinics/<int:clinic_id>/employees/",
        ClinicEmployeesAPIView.as_view(),
        name="clinic-employees"
    ),

    # Create Employee (POST)
    path("employees/", EmployeeCreateAPIView.as_view(), name="employee-create"),

    # Create User (POST)
    path("users/", UserCreateAPIView.as_view(), name="user-create"),

# ==================================================
# Parameter APIs
# ==================================================

    # Create Parameter Value (POST)
    path(
        "parameter-values/",
        ParameterValueCreateAPIView.as_view(),
        name="parameter-value-create"
    ),

    # List Parameter Values by Parameter ID (GET)
    path(
        "parameters/<int:parameter_id>/values/",
        ParameterValueListAPIView.as_view(),
        name="parameter-value-list"
    ),

    # Soft Delete Parameter (PATCH)
    path(
        "parameters/<int:parameter_id>/soft-delete",
        SoftDeleteParameterAPIView.as_view(),
        name="parameter-soft-delete"
    ),

# ==================================================
# Parameter Activation / Inactivation
# ==================================================

    # Activate Parameter (Equipment / Environment) (POST)
    path(
        "parameters/activate/",
        ActivateParameterAPIView.as_view(),
        name="parameter-activate"
    ),

    # Inactivate Parameter (Equipment / Environment) (PATCH)
    path(
        "parameters/inactivate/",
        InactivateParameterAPIView.as_view(),
        name="parameter-inactivate"
    ),

# ==================================================
# Environment APIs
# ==================================================

    # Create Environment under Department (POST)
    path(
        "departments/<int:department_id>/environments/",
        EnvironmentCreateAPIView.as_view(),
        name="environment-create"
    ),

    # Update Environment (PUT)
    path(
        "environments/<int:environment_id>/",
        EnvironmentUpdateAPIView.as_view(),
        name="environment-update"
    ),

    # Get Environment by ID (GET)
    path(
        "environments/<int:environment_id>/get/",
        EnvironmentGetAPIView.as_view(),
        name="environment-get"
    ),

    # Get Full Environment Hierarchy (GET)
    path(
        "environments/<int:environment_id>/full/",
        EnvironmentFullHierarchyAPIView.as_view(),
        name="environment-full-hierarchy"
    ),

    # Activate Environment (POST)
    path(
        "environments/<int:environment_id>/activate/",
        EnvironmentActivateAPIView.as_view(),
        name="environment-activate"
    ),

    # Inactivate Environment (PATCH)
    path(
        "environments/<int:environment_id>/inactivate/",
        EnvironmentInactivateAPIView.as_view(),
        name="environment-inactivate"
    ),

    # Soft Delete Environment (PATCH)
    path(
        "environments/<int:environment_id>/delete/",
        EnvironmentSoftDeleteAPIView.as_view(),
        name="environment-soft-delete"
    ),

# ==================================================
# Environment Parameter APIs
# ==================================================

    # Patch Environment Parameter (PATCH)
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

    # List Environment Parameter Values (GET)
    path(
        "environment-parameters/<int:env_parameter_id>/values/",
        EnvironmentParameterValueListAPIView.as_view(),
        name="environment-parameter-values"
    ),

    # Soft Delete Environment Parameter (PATCH)
    path(
        "environment-parameters/<int:parameter_id>/delete/",
        EnvironmentParameterSoftDeleteAPIView.as_view(),
        name="environment-parameter-soft-delete"
    ),

# ==================================================
# Task Event APIs
# ==================================================

    # List all Task Events (GET)
    path("task-events/", TaskEventListAPIView.as_view(), name="task-event-list"),

    # Create Task Event (POST)
    path("task-events/create/", TaskEventCreateAPIView.as_view(), name="task-event-create"),

    # Get Task Event by ID (GET)
    path(
        "task-events/<int:task_event_id>/",
        TaskEventListAPIView.as_view(),
        name="task-event-get"
    ),
]
