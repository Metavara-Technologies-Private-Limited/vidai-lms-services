import uuid
from django.db import models
from .template_mail import TemplateMail

class TemplateMailDocument(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    template = models.ForeignKey(
        TemplateMail,
        on_delete=models.CASCADE,
        related_name="documents"
    )

    file = models.FileField(upload_to="template_mail_documents/")

    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "restapi_template_mail_document"
