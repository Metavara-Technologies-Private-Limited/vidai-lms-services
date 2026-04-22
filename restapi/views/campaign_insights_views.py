import logging
import traceback
import requests

from django.utils import timezone
from django.conf import settings

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from restapi.models import Campaign, CampaignSocialMediaConfig
from restapi.models.social_account import SocialAccount

logger = logging.getLogger(__name__)


class CampaignInsightsTriggerAPIView(APIView):
    """
    POST /api/campaign/insights/trigger/
    Called by FE when campaign is clicked/opened
    """
    def post(self, request):
        try:
            campaign_id = request.data.get("campaign_id")

            if not campaign_id:
                return Response(
                    {"error": "campaign_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            campaign = Campaign.objects.get(id=campaign_id)

            # Get clinic from campaign directly — no resolve_request_clinic needed
            clinic_id = campaign.clinic_id

            google_account = SocialAccount.objects.filter(
                clinic_id=clinic_id,
                platform="google",
                is_active=True
            ).first()

            if not google_account:
                return Response(
                    {"error": "Google Ads not connected"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            payload = {
                "event":             "google_ads_insights_requested",
                "campaign_id":       str(campaign_id),
                "clinic_id":         str(clinic_id),
                "campaign_name":     campaign.campaign_name,
                "refresh_token":     google_account.user_token,
                "customer_id":       str(google_account.customer_id or "").replace("-", ""),
                "login_customer_id": str(
                    getattr(settings, "GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")
                ).replace("-", ""),
                "developer_token":   settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                "client_id":         settings.GOOGLE_CLIENT_ID,
                "client_secret":     settings.GOOGLE_CLIENT_SECRET,
                "callback_url":      f"{settings.BACKEND_BASE_URL}/api/campaign/insights/callback/",
            }

            zapier_resp = requests.post(
                settings.ZAPIER_WEBHOOK_INSIGHTS_URL,
                json=payload,
                timeout=10
            )

            logger.info(
                "[InsightsTrigger] Sent to Zapier: %s | response: %s",
                campaign_id, zapier_resp.status_code
            )

            return Response({
                "success":     True,
                "message":     "Insights fetch triggered",
                "campaign_id": str(campaign_id),
            })

        except Campaign.DoesNotExist:
            return Response(
                {"error": "Campaign not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error("[InsightsTrigger] Error: %s", traceback.format_exc())
            return Response({"error": str(e)}, status=500)


class CampaignInsightsCallbackAPIView(APIView):
    """
    POST /api/campaign/insights/callback/
    Zapier calls this after fetching insights — NO auth required
    """
    authentication_classes = []
    permission_classes     = [AllowAny]

    def post(self, request):
        try:
            data        = request.data
            campaign_id = data.get("campaign_id")
            platform    = data.get("platform", "google_ads")

            print("[InsightsCallback] Received:", data)

            if not campaign_id:
                return Response(
                    {"error": "campaign_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            config = CampaignSocialMediaConfig.objects.filter(
                campaign_id=campaign_id,
                platform_name=platform
            ).first()

            if not config:
                return Response(
                    {"error": f"No config found for campaign {campaign_id} platform {platform}"},
                    status=status.HTTP_404_NOT_FOUND
                )

            config.insights = {
                "impressions": data.get("impressions", 0),
                "clicks":      data.get("clicks", 0),
                "ctr":         data.get("ctr", 0),
                "avg_cpc":     data.get("avg_cpc", 0),
                "cost":        data.get("cost", 0),
                "conversions": data.get("conversions", 0),
                "fetched_at":  str(timezone.now()),
            }
            config.save(update_fields=["insights"])

            logger.info(
                "[InsightsCallback] Saved insights for campaign %s platform %s",
                campaign_id, platform
            )

            return Response({
                "success":     True,
                "campaign_id": campaign_id,
                "platform":    platform,
            })

        except Exception as e:
            logger.error("[InsightsCallback] Error: %s", traceback.format_exc())
            return Response({"error": str(e)}, status=500)
            