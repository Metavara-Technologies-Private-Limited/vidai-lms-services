# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import logging
import traceback

from django.core.cache import cache
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from restapi.models import Lead

logger = logging.getLogger(__name__)

# =====================================================
# MAIL INSIGHTS APIs
# =====================================================
class MailInsightsReceiveAPIView(APIView):
    """
    POST /api/mail-insights/

    Receives mail insight counts pushed from Zapier.

    CRITICAL FIX — accumulate, never overwrite:
      Each Zapier Zap sends only ITS own field, e.g.:
        Appointment Booked Zap  →  { "appointments_booked": 1 }
        Lead Created Zap        →  { "leads_created": 1 }

      We READ the existing cache first, then ADD the incoming delta.
      A "leads_created=1" POST can NEVER reset appointments_booked to 0.

    Cache TTL: 30 days (2592000 seconds) — survives server restarts longer.
    """

    def post(self, request):
        try:
            data = request.data

            # ── Step 1: Load whatever is currently cached ──────────────────
            existing = cache.get("mail_insights") or {
                "leads_created":       0,
                "appointments_booked": 0,
                "leads_updated":       0,
                "last_synced":         None,
            }

            # ── Step 2: Only add what Zapier actually sent this time ───────
            # If key is absent from POST body → default 0 → no change to total
            incoming_leads        = int(data.get("leads_created", 0))
            incoming_appointments = int(data.get("appointments_booked", 0))
            incoming_updated      = int(data.get("leads_updated", 0))

            payload = {
                "leads_created":       existing["leads_created"]       + incoming_leads,
                "appointments_booked": existing["appointments_booked"] + incoming_appointments,
                "leads_updated":       existing["leads_updated"]       + incoming_updated,
                "last_synced":         timezone.now().isoformat(),
            }

            # ── Step 3: Save accumulated totals for 30 days ───────────────
            cache.set("mail_insights", payload, timeout=2592000)

            logger.info(
                f"[MailInsights] POST received | "
                f"incoming appts={incoming_appointments} leads={incoming_leads} | "
                f"new totals={payload}"
            )
            return Response({"status": "received", "data": payload}, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Mail Insights Receive Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MailInsightsGetAPIView(APIView):
    """
    GET /api/mail-insights/get/

    Returns accumulated mail insight counts for the React dashboard KPI cards.

    DB FALLBACK (so KPI cards NEVER show 0 even if cache is cleared):
      1. Try cache first  → fast, always current after Zapier fires
      2. Cache miss?      → count Lead rows directly from DB
                            leads_created       = total non-deleted leads
                            appointments_booked = leads where status contains "appointment"
         Also repopulates cache so the next request is fast again.
    """

    def get(self, request):
        try:
            payload = cache.get("mail_insights")

            if not payload:
                # ── Cache miss: rebuild counts from DB ─────────────────────
                appointments_count = Lead.objects.filter(
                    is_deleted=False,
                    lead_status__icontains="appointment"
                ).count()

                leads_count = Lead.objects.filter(is_deleted=False).count()

                payload = {
                    "leads_created":       leads_count,
                    "appointments_booked": appointments_count,
                    "leads_updated":       0,
                    "last_synced":         None,
                    "_source":             "db_fallback",  # visible in API response for debugging
                }

                # Repopulate cache so next call is fast
                cache.set("mail_insights", payload, timeout=2592000)
                logger.info(f"[MailInsights] Cache miss — rebuilt from DB: {payload}")

            return Response(payload, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Mail Insights Get Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MailInsightsResetAPIView(APIView):
    """
    POST /api/mail-insights/reset/

    Resets all mail insight counts back to 0.
    Use this if counts get corrupted or for testing a fresh start.

    Example:
      POST http://localhost:8000/api/mail-insights/reset/
      → { "status": "reset", "data": { "leads_created": 0, ... } }
    """

    def post(self, request):
        try:
            payload = {
                "leads_created":       0,
                "appointments_booked": 0,
                "leads_updated":       0,
                "last_synced":         timezone.now().isoformat(),
            }
            cache.set("mail_insights", payload, timeout=604800)
            logger.info("Mail Insights cache reset to 0.")
            return Response({"status": "reset", "data": payload}, status=status.HTTP_200_OK)
        except Exception:
            logger.error("Mail Insights Reset Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

