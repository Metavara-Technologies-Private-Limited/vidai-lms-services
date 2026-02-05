import uuid
from django.db import models
from django.utils import timezone

class Campaign(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    clinic = models.ForeignKey(
        "Clinic",
        on_delete=models.CASCADE,
        related_name="campaigns"
    )

    campaign_name = models.CharField(max_length=255)
    campaign_description = models.TextField(blank=True)
    campaign_objective = models.CharField(max_length=100)   # validate later
    target_audience = models.CharField(max_length=100)      # validate later

    start_date = models.DateField()
    end_date = models.DateField()

    adv_accounts = models.IntegerField(null=True, blank=True)

    ORGANIC = 1
    PAID = 2
    CAMPAIGN_MODE_CHOICES = (
        (ORGANIC, "Organic Posting"),
        (PAID, "Paid Advertising"),
    )
    campaign_mode = models.IntegerField(choices=CAMPAIGN_MODE_CHOICES)

    campaign_content = models.TextField(blank=True)

    selected_start = models.DateTimeField()
    selected_end = models.DateTimeField()
    enter_time = models.TimeField()

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False          # 🔐 VERY IMPORTANT
        db_table = "restapi_campaign"        # 👈 must match EXISTING DB table

