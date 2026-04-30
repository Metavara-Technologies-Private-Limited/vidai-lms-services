import uuid
from django.db import models
from .reputation import ReviewRequest


class ReviewRequestDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review_request = models.ForeignKey(
        ReviewRequest,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    file = models.FileField(upload_to="review_request_documents/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "restapi_review_request_document"

    def __str__(self):
        return f"ReviewRequestDocument - {self.review_request_id}"
