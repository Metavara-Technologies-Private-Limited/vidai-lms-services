import uuid
from django.db import models
from django.utils import timezone

from .campaign import Campaign


class CampaignSocialPost(models.Model):
    """
    Stores execution results of social media posts
    triggered via Zapier (Facebook / LinkedIn).

    This is NOT configuration.
    This tracks actual posting history and status.
    """

    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"

    PLATFORM_CHOICES = (
        (FACEBOOK, "Facebook"),
        (LINKEDIN, "LinkedIn"),
    )

    PENDING = "pending"
    POSTED = "posted"
    FAILED = "failed"

    STATUS_CHOICES = (
        (PENDING, "Pending"),
        (POSTED, "Posted"),
        (FAILED, "Failed"),
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="social_posts"
    )

    platform_name = models.CharField(
        max_length=50,
        choices=PLATFORM_CHOICES
    )

    post_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="ID returned by Facebook/LinkedIn after successful post"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDING
    )

    error_message = models.TextField(
        null=True,
        blank=True
    )

    requested_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When LMS triggered the post"
    )

    synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When Zapier callback updated the status"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ---------------------------------------------------
    # Utility Methods
    # ---------------------------------------------------

    def mark_posted(self, post_id):
        self.post_id = post_id
        self.status = self.POSTED
        self.synced_at = timezone.now()
        self.error_message = None
        self.save(update_fields=[
            "post_id",
            "status",
            "synced_at",
            "error_message",
            "updated_at"
        ])

    def mark_failed(self, error_message):
        self.status = self.FAILED
        self.synced_at = timezone.now()
        self.error_message = error_message
        self.save(update_fields=[
            "status",
            "synced_at",
            "error_message",
            "updated_at"
        ])

    def __str__(self):
        return f"{self.campaign.campaign_name} - {self.platform_name} ({self.status})"
