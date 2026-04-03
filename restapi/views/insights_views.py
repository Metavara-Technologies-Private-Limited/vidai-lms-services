# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import logging
import traceback

from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from restapi.models import Campaign, MarketingEvent, CampaignEmailConfig
from restapi.models.social_account import SocialAccount

from restapi.services.campaign_social_post_service import get_facebook_post_insights
from restapi.services.mailchimp_service import get_mailchimp_campaign_report
from restapi.services.zapier_service import send_to_zapier_mailchimp_insights

logger = logging.getLogger(__name__)

class CampaignFacebookInsightsAPIView(APIView):
    def get(self, request, campaign_id):
        campaign = get_object_or_404(Campaign, id=campaign_id)

        if not campaign.post_id:
            return Response({"error": "Campaign has no Facebook post"}, status=400)

        social = SocialAccount.objects.filter(
            clinic=campaign.clinic, platform="facebook", is_active=True
        ).first()

        if not social:
            return Response({"error": "Facebook not connected"}, status=400)

        token = social.access_token
        print("🔑 Using token:", token[:30] if token else "NONE")

        insights = get_facebook_post_insights(campaign.post_id, token)
        return Response({"post_id": campaign.post_id, "insights": insights})
    

    # =====================================================
# NEW: CAMPAIGN MAILCHIMP INSIGHTS API (GET via Zapier)
# GET /api/campaigns/<campaign_id>/mailchimp-insights/
#
# Flow:
#   1. FE calls GET /api/campaigns/<id>/mailchimp-insights/
#   2. BE fetches directly from Mailchimp API (fast, immediate result)
#   3. ✅ Saves insights to CampaignEmailConfig.insights JSONField (persistent cache in DB)
#      → All insight data stored in ONE JSON column (cleaner, no schema change for new keys)
#      → Dashboard always shows last known data even if Mailchimp is down
#   4. Also saves to MarketingEvent DB (audit trail)
#   5. Also fires send_to_zapier_mailchimp_insights() for any Zapier automations
#   6. Returns full insights JSON to FE
# =====================================================
class CampaignMailchimpInsightsAPIView(APIView):
    """
    GET /api/campaigns/<campaign_id>/mailchimp-insights/

    Fetches Mailchimp campaign insights (opens, clicks, bounces, etc.).
    - Reads directly from Mailchimp API for immediate response
    - Saves result to CampaignEmailConfig.insights JSONField (persistent cache)
      → Single JSON column: emails_sent, opens, open_rate, clicks, click_rate,
        bounces, unsubscribes, last_open, last_click, synced_at
    - Saves result to MarketingEvent DB for audit/history
    - Also triggers Zapier webhook (ZAPIER_WEBHOOK_MAILCHIMP_INSIGHTS_URL)
      so Zapier can react to the insights fetch event

    Response:
        {
            "campaign_id":           "<uuid>",
            "mailchimp_campaign_id": "<mailchimp-id>",
            "campaign_name":         "Pallavi",
            "insights": {
                "emails_sent":   6,
                "opens":         3,
                "open_rate":     "50.0%",
                "clicks":        1,
                "click_rate":    "16.7%",
                "bounces":       0,
                "unsubscribes":  0,
                "last_open":     "2026-03-10T07:18:00",
                "last_click":    "2026-03-10T07:20:00"
            }
        }
    """

    def get(self, request, campaign_id):
        try:
            # Same logic as your POST → consistency
            email_config = (
                CampaignEmailConfig.objects
                .filter(campaign_id=campaign_id)
                .order_by("-created_at")
                .first()
            )

            if not email_config:
                return Response(
                    {"error": "No email config found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not email_config.mailchimp_campaign_id:
                return Response(
                    {"error": "No Mailchimp campaign ID found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Trigger Zapier
            send_to_zapier_mailchimp_insights(
                {
                    "event": "mailchimp_insights_requested",
                    "campaign_id": str(campaign_id),
                    "mailchimp_campaign_id": email_config.mailchimp_campaign_id,
                }
            )

            return Response({"message": "Insights fetch triggered"})

        except Exception:
            logger.error("Mailchimp Insights Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

            # ── Step 1: Fetch directly from Mailchimp API ──────────────────
            # report = get_mailchimp_campaign_report(campaign.mailchimp_campaign_id)

            # if not report:
            #     return Response(
            #         {"error": "Could not fetch Mailchimp report. The campaign may not have been sent yet."},
            #         status=status.HTTP_400_BAD_REQUEST,
            #     )

            # ── Step 2: Save insights to CampaignEmailConfig (persistent DB cache) ──
            # Stores ALL insight data in the single insights JSONField.
            # This means the dashboard ALWAYS has last known data
            # even if Mailchimp API is temporarily unavailable.
            # No individual columns — just one clean JSON dict.
            # email_config = campaign.email_configs.filter(is_active=True).first()
            # if email_config:
            #     # ── Save all insight data to the single insights JSONField ──
            #     email_config.insights = {
            #         "emails_sent":  report.get("emails_sent", 0),
            #         "opens":        report.get("opens", 0),
            #         "open_rate":    report.get("open_rate", 0),
            #         "clicks":       report.get("clicks", 0),
            #         "click_rate":   report.get("click_rate", 0),
            #         "bounces":      report.get("bounces", 0),
            #         "unsubscribes": report.get("unsubscribes", 0),
            #         "last_open":    report.get("last_open"),    # stored as ISO string — no DateTimeField needed
            #         "last_click":   report.get("last_click"),   # stored as ISO string — no DateTimeField needed
            #         "synced_at":    timezone.now().isoformat(),
            #     }

            #     # ── Single save — only the insights JSON column ──
            #     email_config.save(update_fields=["insights"])

            #     logger.info(
            #         f"[MailchimpInsights] Saved to CampaignEmailConfig.insights (JSONField) "
            #         f"id={email_config.id} for campaign: {campaign_id}"
            #     )
            # else:
            #     logger.warning(
            #         f"[MailchimpInsights] No active CampaignEmailConfig found for campaign: {campaign_id}. "
            #         f"Insights not cached to email config table."
            #     )

            # # ── Step 3: Also save to MarketingEvent DB (audit trail) ───────
            # MarketingEvent.objects.create(
            #     source=MarketingEvent.Source.MAILCHIMP,
            #     event_type="campaign_insights_fetched",
            #     payload={
            #         "campaign_id":            str(campaign_id),
            #         "mailchimp_campaign_id":  campaign.mailchimp_campaign_id,
            #         "campaign_name":          campaign.campaign_name,
            #         "emails_sent":            report.get("emails_sent", 0),
            #         "opens":                  report.get("opens", 0),
            #         "open_rate":              report.get("open_rate", 0),
            #         "clicks":                 report.get("clicks", 0),
            #         "click_rate":             report.get("click_rate", 0),
            #         "bounces":                report.get("bounces", 0),
            #         "unsubscribes":           report.get("unsubscribes", 0),
            #         "last_open":              report.get("last_open"),
            #         "last_click":             report.get("last_click"),
            #     }
            # )

            # logger.info(
            #     f"[MailchimpInsights] Fetched & saved for campaign: {campaign_id} "
            #     f"| mailchimp_id: {campaign.mailchimp_campaign_id}"
            # )

            # # ── Step 4: Also trigger Zapier for any downstream automations ─
            # # This fires-and-forgets — insights are already in the response
            # # Zapier can use this to: send Slack alerts, update sheets, etc.
            # send_to_zapier_mailchimp_insights({
            #     "event":                  "mailchimp_insights_requested",
            #     "campaign_id":            str(campaign_id),
            #     "mailchimp_campaign_id":  campaign.mailchimp_campaign_id,
            #     "campaign_name":          campaign.campaign_name,
            #     "emails_sent":            report.get("emails_sent", 0),
            #     "opens":                  report.get("opens", 0),
            #     "open_rate":              report.get("open_rate", 0),
            #     "clicks":                 report.get("clicks", 0),
            #     "click_rate":             report.get("click_rate", 0),
            #     "bounces":                report.get("bounces", 0),
            #     "unsubscribes":           report.get("unsubscribes", 0),
            #     "last_open":              report.get("last_open"),
            #     "last_click":             report.get("last_click"),
            # })

            # ── Step 5: Return insights to FE ──────────────────────────────
            # return Response(
            #     {
            #         "campaign_id":           str(campaign_id),
            #         "mailchimp_campaign_id": campaign.mailchimp_campaign_id,
            #         "campaign_name":         campaign.campaign_name,
            #         "insights": {
            #             "emails_sent":   report.get("emails_sent", 0),
            #             "opens":         report.get("opens", 0),
            #             "open_rate":     f"{report.get('open_rate', 0)}%",
            #             "clicks":        report.get("clicks", 0),
            #             "click_rate":    f"{report.get('click_rate', 0)}%",
            #             "bounces":       report.get("bounces", 0),
            #             "unsubscribes":  report.get("unsubscribes", 0),
            #             "last_open":     report.get("last_open"),
            #             "last_click":    report.get("last_click"),
            #         },
            #     },
            #     status=status.HTTP_200_OK,
            # )

# =====================================================
# NEW: MAILCHIMP INSIGHTS CALLBACK API (POST from Zapier)
# POST /api/mailchimp/insights-callback/
#
# Flow:
#   Zapier receives the insights event from ZAPIER_WEBHOOK_MAILCHIMP_INSIGHTS_URL
#   Zapier processes it (e.g. fetches extra data, sends Slack notification)
#   Zapier POSTs back here with processed insights data
#   We store the callback in MarketingEvent DB
# =====================================================
# class MailchimpInsightsCallbackAPIView(APIView):
#     """
#     POST /api/mailchimp/insights-callback/

#     Receives Mailchimp insights data back from Zapier.
#     Stores the result in MarketingEvent DB with event_type='campaign_insights_callback'.

#     Expected payload from Zapier:
#         {
#             "campaign_id":           "<uuid>",
#             "mailchimp_campaign_id": "<mailchimp-id>",
#             "campaign_name":         "...",
#             "emails_sent":           6,
#             "opens":                 3,
#             "open_rate":             50.0,
#             "clicks":                1,
#             "click_rate":            16.7,
#             "bounces":               0,
#             "unsubscribes":          0,
#             "last_open":             "2026-03-10T07:18:00",
#             "last_click":            "2026-03-10T07:20:00"
#         }
#     """

#     def post(self, request):
#         try:
#             data = request.data

#             print("📩 Mailchimp Insights Callback received:")
#             print(data)

#             # ── Save callback payload to MarketingEvent DB ─────────────────
#             MarketingEvent.objects.create(
#                 source=MarketingEvent.Source.MAILCHIMP,
#                 event_type="campaign_insights_callback",
#                 payload={
#                     "campaign_id":           data.get("campaign_id"),
#                     "mailchimp_campaign_id": data.get("mailchimp_campaign_id"),
#                     "campaign_name":         data.get("campaign_name"),
#                     "emails_sent":           data.get("emails_sent", 0),
#                     "opens":                 data.get("opens", 0),
#                     "open_rate":             data.get("open_rate", 0),
#                     "clicks":                data.get("clicks", 0),
#                     "click_rate":            data.get("click_rate", 0),
#                     "bounces":               data.get("bounces", 0),
#                     "unsubscribes":          data.get("unsubscribes", 0),
#                     "last_open":             data.get("last_open"),
#                     "last_click":            data.get("last_click"),
#                 }
#             )

#             logger.info(
#                 f"[MailchimpInsights] Callback stored for campaign: "
#                 f"{data.get('campaign_id')} | mailchimp_id: {data.get('mailchimp_campaign_id')}"
#             )

#             return Response(
#                 {
#                     "status":      "received",
#                     "campaign_id": data.get("campaign_id"),
#                 },
#                 status=status.HTTP_200_OK,
#             )

#         except Exception:
#             logger.error(
#                 "Mailchimp Insights Callback Error:\n" + traceback.format_exc()
#             )
#             return Response(
#                 {"error": "Internal Server Error"},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             )


class MailchimpInsightsCallbackAPIView(APIView):
    def post(self, request):
        try:
            data = request.data

            print("📩 Mailchimp Insights Callback received:")
            print(data)

            campaign_id = data.get("campaign_id")

            # Get latest email config
            email_config = (
                CampaignEmailConfig.objects.filter(campaign_id=campaign_id)
                .order_by("-created_at")
                .first()
            )

            if not email_config:
                return Response({"error": "No email config found"}, status=400)

            # Save insights JSON (MAIN FIX)
            email_config.insights = {
                "emails_sent": data.get("emails_sent", 0),
                "opens": data.get("opens", 0),
                "open_rate": data.get("open_rate", 0),
                "clicks": data.get("clicks", 0),
                "click_rate": data.get("click_rate", 0),
                "bounces": data.get("hard_bounces", 0) + data.get("soft_bounces", 0),
                "unsubscribes": data.get("unsubscribes", 0),
                "last_open": data.get("last_open"),
                "last_click": data.get("last_click"),
                "synced_at": timezone.now().isoformat(),
            }

            email_config.save(update_fields=["insights"])

            # Optional: keep audit log
            MarketingEvent.objects.create(
                source=MarketingEvent.Source.MAILCHIMP,
                event_type="campaign_insights_callback",
                payload=data,
            )

            return Response({"status": "saved", "campaign_id": campaign_id})

        except Exception:
            logger.error(
                "Mailchimp Insights Callback Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
