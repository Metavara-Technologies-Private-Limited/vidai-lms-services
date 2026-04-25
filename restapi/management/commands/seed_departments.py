from django.core.management.base import BaseCommand
from restapi.models import Clinic, Department


class Command(BaseCommand):
    help = "Seed a default 'General' department for every clinic that has none."

    def handle(self, *args, **kwargs):
        clinics_seeded = 0
        for clinic in Clinic.objects.all():
            if not Department.objects.filter(clinic=clinic).exists():
                Department.objects.create(
                    clinic=clinic,
                    name="General",
                    is_active=True,
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Created 'General' dept for clinic: {clinic.name} (id={clinic.id})"
                    )
                )
                clinics_seeded += 1

        if clinics_seeded == 0:
            self.stdout.write("All clinics already have at least one department. Nothing to do.")
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\nDone. Seeded {clinics_seeded} clinic(s).")
            )
