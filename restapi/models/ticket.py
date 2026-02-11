import uuid
from django.db import models
from .lab import Lab
from .department import Department
from .employee import Employee


class Ticket(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    STATUS_CHOICES = [
        ("new", "New"),
        ("pending", "Pending"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]

    ticket_no = models.CharField(max_length=20, unique=True)

    subject = models.CharField(max_length=255)
    description = models.TextField()

    lab = models.ForeignKey(
        Lab,
        on_delete=models.CASCADE,
        related_name="tickets"
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="tickets"
    )

    requested_by = models.CharField(max_length=255)

    assigned_to = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets"
    )

    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="new"
    )

    due_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    def __str__(self):
        return self.ticket_no
