import uuid

from django.db import models


class LeadFormField(models.Model):
    FIELD_TYPE_CHOICES = (
        ("text", "Text"),
        ("number", "Number"),
        ("date", "Date"),
        ("dropdown", "Dropdown"),
        ("textarea", "Textarea"),
        ("email", "Email"),
        ("phone", "Phone"),
        ("multi_select", "Multi Select"),
        ("boolean", "Boolean"),
        ("file", "File"),
    )

    STAGE_FIELD_TYPE_MAP = {
        "text": "text",
        "textarea": "text",
        "email": "text",
        "phone": "text",
        "file": "text",
        "number": "number",
        "date": "date",
        "dropdown": "dropdown",
        "multi_select": "dropdown",
        "boolean": "dropdown",
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    field_key = models.CharField(max_length=100, unique=True)
    model_field = models.CharField(max_length=100, blank=True, default="")
    field_label = models.CharField(max_length=150)
    field_type = models.CharField(max_length=30, choices=FIELD_TYPE_CHOICES, default="text")
    options_source = models.CharField(max_length=100, blank=True, default="")
    form_step = models.PositiveSmallIntegerField(default=1)
    section = models.CharField(max_length=100, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    @property
    def stage_field_type(self):
        return self.STAGE_FIELD_TYPE_MAP.get(self.field_type, "text")

    class Meta:
        db_table = "restapi_lead_form_field"
        ordering = ["sort_order", "field_label"]
        indexes = [
            models.Index(fields=["field_key"]),
            models.Index(fields=["is_active", "sort_order"]),
        ]

    def __str__(self):
        return self.field_label
