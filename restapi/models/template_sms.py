import uuid
from django.db import models
from .clinic import Clinic
from .employee import Employee

class TemplateSMS(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="sms_templates"
    )

    name = models.CharField(max_length=255)

    use_case = models.CharField(max_length=100)

    body = models.TextField()

    created_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True
    )

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "restapi_template_sms"
