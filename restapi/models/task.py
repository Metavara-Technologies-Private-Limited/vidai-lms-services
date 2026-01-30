from django.db import models
from .employee import Employee
from .department import Department

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

    TIMER_IDLE = "IDLE"
    TIMER_RUNNING = "RUNNING"
    TIMER_PAUSED = "PAUSED"
    TIMER_STOPPED = "STOPPED"

    TIMER_STATUS_CHOICES = (
        (TIMER_IDLE, "Idle"),
        (TIMER_RUNNING, "Running"),
        (TIMER_PAUSED, "Paused"),
        (TIMER_STOPPED, "Stopped"),
    )

    name = models.CharField(max_length=255)

    task_event = models.ForeignKey(
        "Task_Event",   # ✅ FIXED
        on_delete=models.CASCADE,
        related_name="tasks"
    )

    assignment = models.ForeignKey(Employee, on_delete=models.CASCADE)

    is_deleted = models.BooleanField(default=False)

    due_date = models.DateTimeField()
    description = models.CharField(max_length=500)

    status = models.IntegerField(
        choices=STATUS_CHOICES,
        default=TODO
    )

    # ⏱ TIMER FIELDS
    timer_status = models.CharField(
        max_length=20,
        choices=TIMER_STATUS_CHOICES,
        default=TIMER_IDLE
    )
    total_tracked_sec = models.IntegerField(default=0)
    timer_started_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)






# =========================
# Sub Task
# =========================
class SubTask(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    assignment = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE
    )
    is_deleted = models.BooleanField(default=False)
    due_date = models.DateTimeField()

    name = models.CharField(max_length=500)  # ✅ RENAMED from description

    status = models.IntegerField(
        choices=Task.STATUS_CHOICES,
        default=Task.TODO
    )
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

# =========================
# Task Event
# =========================
class Task_Event(models.Model):
    name = models.CharField(max_length=255)

    dep = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="task_events"
    )

    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "task_event"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name