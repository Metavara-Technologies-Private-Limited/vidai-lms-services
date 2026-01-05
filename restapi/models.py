from django.db import models
from django.conf import settings



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
    modified_at = models.DateTimeField(auto_now=True)
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
    modified_at = models.DateTimeField(auto_now=True)
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
    modified_at = models.DateTimeField(auto_now=True)
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
    modified_at = models.DateTimeField(auto_now=True)
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
    modified_at = models.DateTimeField(auto_now=True)

# =========================
# Employee (assignment_id)
# =========================
class Employee(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    dep = models.ForeignKey(Department, on_delete=models.CASCADE)
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE)
    emp_type = models.CharField(max_length=100)
    emp_name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    

# =========================
# Event
# =========================
class Event(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    assignment = models.ForeignKey(  # assignment_id
        Employee,
        on_delete=models.CASCADE
    )
    event_name = models.CharField(max_length=200)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)


# =========================
# Event ↔ Equipment
# =========================
class EventEquipment(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    equipment = models.ForeignKey(Equipments, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("event", "equipment")


# =========================
# Event Schedule
# =========================
class EventSchedule(models.Model):
    ONE_TIME = 1
    WEEKLY = 2
    MONTHLY = 3

    TYPE_CHOICES = (
        (ONE_TIME, "One Time"),
        (WEEKLY, "Weekly"),
        (MONTHLY, "Monthly"),
    )

    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    type = models.IntegerField(choices=TYPE_CHOICES)

    from_time = models.DateTimeField()
    to_time = models.DateTimeField()

    one_time_date = models.DateTimeField(null=True, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    months = models.JSONField(null=True, blank=True)
    days = models.JSONField(null=True, blank=True)
    recurring_duration = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)


# =========================
# Assignee ↔ Event
# =========================
class AssigneeEvent(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    assignment = models.ForeignKey(  # assignment_id
        Employee,
        on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("event", "assignment")


# =========================
# Event ↔ Parameter
# =========================
class EventParameter(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    parameter = models.ForeignKey(Parameters, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("event", "parameter")



# =========================
# Task
# =========================
class Task(models.Model):
    TODO = 0
    IN_PROGRESS = 1
    COMPLETED = 2

    STATUS_CHOICES = (
        (TODO, "Todo"),
        (IN_PROGRESS, "In Progress"),
        (COMPLETED, "Completed"),
    )

    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    assignment = models.ForeignKey(  # assignment_id
        Employee,
        on_delete=models.CASCADE
    )
    is_deleted = models.BooleanField(default=False)
    due_date = models.DateTimeField()
    description = models.CharField(max_length=500)
    status = models.IntegerField(choices=STATUS_CHOICES, default=TODO)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)



# =========================
# Sub Task
# =========================
class SubTask(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    assignment = models.ForeignKey(  # assignment_id
        Employee,
        on_delete=models.CASCADE
    )
    is_deleted = models.BooleanField(default=False)
    due_date = models.DateTimeField()
    description = models.CharField(max_length=500)
    status = models.IntegerField(choices=Task.STATUS_CHOICES, default=Task.TODO)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)



# =========================
# Document
# =========================
class Document(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    document_name = models.CharField(max_length=255)
    data = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
