import uuid
from django.db import models


class Campaign(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    clinic = models.ForeignKey(
        "Clinic",
        on_delete=models.CASCADE,
        related_name="campaigns"
    )

    campaign_name = models.CharField(max_length=255)
    campaign_description = models.TextField(blank=True)
    campaign_objective = models.CharField(max_length=100)
    target_audience = models.CharField(max_length=100)

    start_date = models.DateField()
    end_date = models.DateField()

    adv_accounts = models.IntegerField(null=True, blank=True)

    # ----------------------------
    # CAMPAIGN MODE
    # ----------------------------
    ORGANIC = 1
    PAID = 2
    EMAIL = 3

    CAMPAIGN_MODE_CHOICES = (
        (ORGANIC, "Organic Posting"),
        (PAID, "Paid Advertising"),
        (EMAIL, "Email Campaign"),
    )

    campaign_mode = models.IntegerField(choices=CAMPAIGN_MODE_CHOICES)

    campaign_content = models.TextField(blank=True)

    # ----------------------------
    # ✅ SOCIAL MEDIA POST ID
    # ----------------------------
    post_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Stores social media post ID (Facebook / LinkedIn / Instagram)"
    )

    # ----------------------------
    # ✅ NEW: IMAGE URL FOR SOCIAL POSTS
    # ----------------------------
    image_url = models.URLField(
        max_length=2000,
        null=True,
        blank=True,
        help_text="Public image URL attached to social media posts"
    )

    selected_start = models.DateTimeField(null=True, blank=True)
    selected_end = models.DateTimeField(null=True, blank=True)
    enter_time = models.TimeField(null=True, blank=True)

    # ----------------------------
    # ✅ JSONB COLUMN FOR SOCIAL PLATFORMS
    # ----------------------------
    platform_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Stores Facebook, Instagram, LinkedIn campaign data"
    )

    # ----------------------------
    # ✅ JSONB COLUMN FOR BUDGET
    # ----------------------------
    budget_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Stores campaign budget structure (total, daily, split, spend, etc.)"
    )

    mailchimp_campaign_id = models.CharField(max_length=100, null=True, blank=True)

    fb_campaign_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Facebook Ad Campaign ID created via API"
    )

    # ----------------------------
    # STATUS FIELD
    # ----------------------------
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        LIVE = "live", "Live"
        PAUSED = "paused", "Paused"
        STOPPED = "stopped", "Stopped"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )

    # ----------------------------
    # FLAGS
    # ----------------------------
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    converted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "restapi_campaign"
