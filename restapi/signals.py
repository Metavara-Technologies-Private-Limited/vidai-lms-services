from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from restapi.models import (
    UserProfile,
    Role,
    Employee,
    Lead,
    Ticket,
    TicketTimeline,
)


def _build_display_name(instance: User) -> str:
    full_name = f"{instance.first_name or ''} {instance.last_name or ''}".strip()
    return full_name or instance.username or str(instance.id)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        role = Role.objects.filter(name="User").first()

        UserProfile.objects.create(
            user=instance,
            role=role
        )


@receiver(post_save, sender=User)
def sync_user_display_names(sender, instance, created, **kwargs):
    display_name = _build_display_name(instance)

    employee = Employee.objects.filter(user=instance).first()
    if employee:
        if employee.emp_name != display_name or employee.email != instance.email:
            Employee.objects.filter(id=employee.id).update(
                emp_name=display_name,
                email=instance.email,
            )

        employee_id = employee.id

        Lead.objects.filter(assigned_to_id=employee_id).update(
            assigned_to_name=display_name,
        )
        Lead.objects.filter(personal_id=employee_id).update(
            personal_name=display_name,
        )
        Lead.objects.filter(created_by_id=employee_id).update(
            created_by_name=display_name,
        )
        Lead.objects.filter(updated_by_id=employee_id).update(
            updated_by_name=display_name,
        )

        Ticket.objects.filter(assigned_to_id=employee_id).update(
            assigned_to_name=display_name,
        )

        TicketTimeline.objects.filter(done_by_id=employee_id).update(
            done_by_name=display_name,
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