# restapi/services/referral_service.py

from django.db.models import Count
from restapi.models.referral import ReferralSource


def get_referral_sources(source_type=None, search=None, clinic=None):

    queryset = ReferralSource.objects.select_related("external_clinic", "clinic")

    # 🔹 Filter by logged-in clinic (VERY IMPORTANT)
    if clinic:
        queryset = queryset.filter(clinic=clinic)

    if source_type:
        queryset = queryset.filter(type=source_type)

    if search:
        queryset = queryset.filter(name__icontains=search)

    queryset = queryset.annotate(
        referral_count=Count("leads", distinct=True)
    ).order_by("-id")

    return queryset


def get_dashboard_counts(clinic=None):

    queryset = ReferralSource.objects.all()

    if clinic:
        queryset = queryset.filter(clinic=clinic)

    data = queryset.values("type").annotate(count=Count("id"))

    result = {
        "doctor": 0,
        "corporate_hr": 0,
        "insurance": 0,
        "lab": 0,
        "partner": 0
    }

    for item in data:
        result[item["type"]] = item["count"]

    return result