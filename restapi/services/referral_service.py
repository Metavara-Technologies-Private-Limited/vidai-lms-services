from django.db.models import Count
from restapi.models.referral import ReferralSource
from restapi.models.referral_department import ReferralDepartment
from restapi.models.lead import Lead


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
# 🔹 DASHBOARD COUNTS
# Counts leads per ReferralDepartment for the given clinic.
# Returns: { "Doctors": 5, "Corporate HR": 2, ... }
# =====================================================
def get_dashboard_counts(clinic=None):
    # Get all active referral departments for this clinic
    departments = ReferralDepartment.objects.filter(is_active=True)
    if clinic:
        departments = departments.filter(clinic=clinic)

    # Count leads per department (clinic-scoped)
    lead_qs = Lead.objects.filter(is_deleted=False)
    if clinic:
        lead_qs = lead_qs.filter(clinic=clinic)

    counts_qs = (
        lead_qs
        .exclude(referral_department__isnull=True)
        .values("referral_department__name")
        .annotate(count=Count("id"))
    )

    counts_by_name = {row["referral_department__name"]: row["count"] for row in counts_qs}

    result = {dept.name: counts_by_name.get(dept.name, 0) for dept in departments}

    return result