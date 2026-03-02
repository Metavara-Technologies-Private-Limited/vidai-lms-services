from django.db import models
from .clinic import Clinic


class SocialAccount(models.Model):
    PLATFORM_CHOICES = (
        ("facebook", "Facebook"),
        ("instagram", "Instagram"),
        ("linkedin", "LinkedIn"),
    )

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)

    # Facebook data
    access_token = models.TextField()
    page_id = models.CharField(max_length=100, null=True, blank=True)
    page_name = models.CharField(max_length=255, null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("clinic", "platform")

    def __str__(self):
        return f"{self.clinic} - {self.platform}"
