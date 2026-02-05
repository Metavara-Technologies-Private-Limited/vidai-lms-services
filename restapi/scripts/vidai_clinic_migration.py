import json
import os
from django.conf import settings
from restapi.models import Clinic, Department
from django.db import transaction

JSON_FILE_PATH = os.path.join(
    settings.BASE_DIR,
    "django_rest_main",
    "vidai_clinics.json"
)

@transaction.atomic
def run():
    with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    clinics = data.get("objects", [])

    for clinic_data in clinics:
        clinic, _ = Clinic.objects.get_or_create(
            id=clinic_data["id"],
            defaults={"name": clinic_data["name"]}
        )

        for dept in clinic_data.get("departments", []):
            Department.objects.get_or_create(
                id=dept["id"],
                defaults={
                    "name": dept["name"],
                    "clinic": clinic,
                    "is_active": True
                }
            )

    print(" Vidai clinics & departments migrated successfully")
