from django.core.management.base import BaseCommand
from restapi.models import Clinic, Department


class Command(BaseCommand):
    help = "Ensure each clinic has at least one department"

    def handle(self, *args, **kwargs):
        clinics_seeded = 0

        for clinic in Clinic.objects.all():
            departments = Department.objects.filter(clinic=clinic)

            if not departments.exists():

                dept, created = Department.objects.get_or_create(
                    clinic=clinic,
                    name=f"{clinic.name} Default Department",
                    defaults={"is_active": True},
                )

                if created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Created default dept for clinic: {clinic.name} (id={clinic.id})"
                        )
                    )
                    clinics_seeded += 1

        if clinics_seeded == 0:
            self.stdout.write("All clinics already have departments.")
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\nDone. Seeded {clinics_seeded} clinic(s).")
            )