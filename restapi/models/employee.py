from django.db import models
from django.conf import settings
from .clinic import Clinic
from .department import Department


class Employee(models.Model):
    user       = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    dep        = models.ForeignKey(Department, on_delete=models.CASCADE)
    clinic     = models.ForeignKey(Clinic, on_delete=models.CASCADE)
    emp_type   = models.CharField(max_length=100)
    emp_name   = models.CharField(max_length=200)
    email      = models.EmailField(max_length=255, null=True, blank=True)   # ✅ NEW
    contact_no = models.CharField(max_length=20, null=True, blank=True)    # ✅ NEW
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.emp_name} ({self.emp_type})"