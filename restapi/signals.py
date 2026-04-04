from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from restapi.models import UserProfile, Role


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        role = Role.objects.filter(name="User").first()

        UserProfile.objects.create(
            user=instance,
            role=role
        )