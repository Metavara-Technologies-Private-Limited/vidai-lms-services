from django.db.models import Sum, Avg
from restapi.models.reports import CallLog, CampaignMetrics


# =====================================================
# COMMON FILTER BUILDER (REUSABLE)
# =====================================================
def apply_common_filters(queryset, filters=None, is_call=False):
    """
    Apply filters dynamically to queryset
    """

    if not filters:
        return queryset

    # Clinic filter
    if filters.get("clinic_id"):
        if is_call:
            queryset = queryset.filter(lead__clinic_id=filters["clinic_id"])
        else:
            queryset = queryset.filter(campaign__clinic_id=filters["clinic_id"])

    # Date filter
    if filters.get("from_date") and filters.get("to_date"):
        if is_call:
            queryset = queryset.filter(
                created_at__date__range=[filters["from_date"], filters["to_date"]]
            )
        else:
            queryset = queryset.filter(
                date__range=[filters["from_date"], filters["to_date"]]
            )

    # User filter (only for calls)
    if is_call and filters.get("user_id"):
        queryset = queryset.filter(received_by_id=filters["user_id"])

    # Campaign-specific filters
    if not is_call:

        # Platform filter (JSONField)
        if filters.get("platform"):
            queryset = queryset.filter(
                campaign__platform_data__has_key=filters["platform"]
            )

        # Campaign mode filter
        if filters.get("campaign_mode"):
            queryset = queryset.filter(
                campaign__campaign_mode=filters["campaign_mode"]
            )

    return queryset


# =====================================================
# CALL REPORT SERVICE
# =====================================================
def get_call_report(filters=None):
    queryset = CallLog.objects.all()

    # Apply filters
    queryset = apply_common_filters(queryset, filters, is_call=True)

    total_calls = queryset.count()
    attempted = queryset.filter(call_type="outgoing").count()
    connected = queryset.filter(status="connected").count()

    not_connected = total_calls - connected

    avg_duration = queryset.aggregate(avg=Avg("duration"))["avg"] or 0

    return {
        "total_calls": total_calls,
        "attempted": attempted,
        "connected": connected,
        "not_connected_percentage": round(
            (not_connected / total_calls * 100), 2
        ) if total_calls else 0,
        "avg_duration": round(avg_duration, 2),
    }


# =====================================================
# CAMPAIGN REPORT SERVICE
# =====================================================
def get_campaign_report(filters=None):
    queryset = CampaignMetrics.objects.all()

    # Apply filters
    queryset = apply_common_filters(queryset, filters, is_call=False)

    total = queryset.aggregate(
        impressions=Sum("impressions"),
        clicks=Sum("clicks"),
        conversions=Sum("conversions"),
        spend=Sum("spend"),
        sent=Sum("sent"),
        opened=Sum("opened"),
        unsubscribed=Sum("unsubscribed"),
    )

    impressions = total["impressions"] or 0
    clicks = total["clicks"] or 0
    conversions = total["conversions"] or 0
    spend = total["spend"] or 0
    sent = total["sent"] or 0
    opened = total["opened"] or 0
    unsubscribed = total["unsubscribed"] or 0

    # =========================
    # KPI CALCULATIONS
    # =========================
    ctr = (clicks / impressions * 100) if impressions else 0
    conversion_rate = (conversions / clicks * 100) if clicks else 0
    cpc = (spend / clicks) if clicks else 0
    cpl = (spend / conversions) if conversions else 0

    open_rate = (opened / sent * 100) if sent else 0
    unsubscribe_rate = (unsubscribed / sent * 100) if sent else 0

    return {
        "impressions": impressions,
        "clicks": clicks,
        "conversions": conversions,
        "spend": spend,

        # Ads KPIs
        "ctr": round(ctr, 2),
        "conversion_rate": round(conversion_rate, 2),
        "cpc": round(cpc, 2),
        "cpl": round(cpl, 2),

        # Email KPIs
        "open_rate": round(open_rate, 2),
        "unsubscribe_rate": round(unsubscribe_rate, 2),
    }


# =====================================================
# OPTIONAL: TABLE DATA FETCH (FOR UI TABLES)
# =====================================================
def get_call_logs(filters=None):
    queryset = CallLog.objects.all()
    queryset = apply_common_filters(queryset, filters, is_call=True)
    return queryset.order_by("-created_at")


def get_campaign_metrics(filters=None):
    queryset = CampaignMetrics.objects.all()
    queryset = apply_common_filters(queryset, filters, is_call=False)
    return queryset.order_by("-date")