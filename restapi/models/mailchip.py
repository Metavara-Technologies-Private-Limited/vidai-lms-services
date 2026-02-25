from django.db import models


class MarketingEvent(models.Model):

    class Source(models.TextChoices):
        MAILCHIMP = "mailchimp", "Mailchimp"

    source = models.CharField(
        max_length=50,
        choices=Source.choices,
    )

    event_type = models.CharField(max_length=100)

    payload = models.JSONField()

    created_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "marketing_events"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.source} - {self.event_type}"