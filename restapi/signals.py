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


DEFAULT_REFERRAL_DEPARTMENTS = [
    "Doctors",
    "Corporate HR",
    "Diagnostic Labs",
    "Insurance Partners",
    "Practo",
    "Zoya",
]


@receiver(post_save, sender="restapi.Clinic")
def seed_referral_departments_for_new_clinic(sender, instance, created, **kwargs):
    if not created:
        return
    from restapi.models.referral_department import ReferralDepartment
    for name in DEFAULT_REFERRAL_DEPARTMENTS:
        ReferralDepartment.objects.get_or_create(
            clinic=instance,
            name=name,
            defaults={"is_active": True},
        )