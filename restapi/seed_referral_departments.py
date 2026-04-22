from django.core.management.base import BaseCommand
from restapi.models import Clinic
from restapi.models.referral_department import ReferralDepartment

DEFAULT_DEPARTMENTS = [
    "Doctors",
    "Corporate HR",
    "Diagnostic Labs",
    "Insurance Partners",
    "Practo",
    "Zoya",
]


class Command(BaseCommand):
    help = "Seed the 6 default referral departments for every clinic."

    def handle(self, *args, **kwargs):
        clinics = Clinic.objects.all()
        created_total = 0

        for clinic in clinics:
            for name in DEFAULT_DEPARTMENTS:
                dept, created = ReferralDepartment.objects.get_or_create(
                    clinic=clinic,
                    name=name,
                    defaults={"is_active": True},
                )
                if created:
                    created_total += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Created '{name}' for clinic: {clinic.name} (id={clinic.id})"
                        )
                    )

        if created_total == 0:
            self.stdout.write("All clinics already have all referral departments. Nothing to do.")
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\nDone. Created {created_total} referral department(s).")
            )
