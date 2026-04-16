from django.db.models import Count
from restapi.models.referral import ReferralSource


# =====================================================
# 🔹 GET REFERRAL SOURCES
# =====================================================
def get_referral_sources(department_id=None, search=None, clinic=None):

    queryset = ReferralSource.objects.select_related(
        "external_clinic",
        "clinic",
        "referral_department"
    )

    # 🔥 CLINIC ISOLATION
    if clinic:
        queryset = queryset.filter(clinic=clinic)

    # 🔹 FILTER BY DEPARTMENT
    if department_id:
        queryset = queryset.filter(referral_department_id=department_id)

    # 🔹 SEARCH
    if search:
        queryset = queryset.filter(name__icontains=search)

    queryset = queryset.annotate(
        referral_count=Count("leads", distinct=True)
    ).order_by("-id")

    return queryset


# =====================================================
# 🔹 DASHBOARD COUNTS (🔥 THIS WAS MISSING)
# =====================================================
def get_dashboard_counts(clinic=None):

    queryset = ReferralSource.objects.all()

    # 🔥 CLINIC ISOLATION
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