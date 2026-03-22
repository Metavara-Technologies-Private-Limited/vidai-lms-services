import uuid
from django.db import models
from .clinic import Clinic
from .lead import Lead


class ReviewRequest(models.Model):

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("scheduled", "Scheduled"),
    ]

    MODE_CHOICES = [
        ("email", "Email"),
        ("sms", "SMS"),
        ("whatsapp", "WhatsApp"),
    ]

    COLLECT_CHOICES = [
        ("google", "Google"),
        ("form", "Feedback Form"),
        ("both", "Both"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="review_requests"
    )

    request_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    collect_on = models.CharField(max_length=20, choices=COLLECT_CHOICES)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)

    subject = models.TextField(blank=True)
    message = models.TextField(blank=True)

    schedule_date = models.DateField(null=True, blank=True)
    schedule_time = models.TimeField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.request_name


class ReviewRequestLead(models.Model):

    review_request = models.ForeignKey(
        ReviewRequest,
        on_delete=models.CASCADE,
        related_name="leads"
    )

    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE
    )

    request_sent = models.BooleanField(default=False)
    review_submitted = models.BooleanField(default=False)


class Review(models.Model):

    review_request = models.ForeignKey(
        ReviewRequest,
        on_delete=models.CASCADE,
        related_name="reviews"
    )

    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE
    )

    rating = models.FloatField()
    review_text = models.TextField(blank=True)

    submitted_at = models.DateTimeField(auto_now_add=True)