import logging
import traceback
import requests

from django.conf import settings

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from restapi.models.social_account import SocialAccount
from restapi.services.zapier_service import send_to_zapier_social

logger = logging.getLogger(__name__)


class GoogleAdsCampaignCreateAPIView(APIView):
    """
    POST /api/google-ads/create/
    Sends a Google Ads campaign creation request to Zapier with fallback auth.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = request.data

            # ----------------------------------------------------------
            # 1. Validate required fields
            # ----------------------------------------------------------
            clinic_id   = data.get("clinic_id")
            customer_id = data.get("customer_id")  # try frontend first

            if not clinic_id:
                return Response(
                    {"success": False, "error": "clinic_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not data.get("campaign_name"):
                return Response(
                    {"success": False, "error": "campaign_name is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ----------------------------------------------------------
            # 2. Load Tokens (Database -> settings.py fallback)
            # ----------------------------------------------------------
            google_account = SocialAccount.objects.filter(
                clinic_id=clinic_id,
                platform="google",
                is_active=True,
            ).first()

            # If customer_id not sent by frontend, pull from DB automatically
            if not customer_id and google_account:
                customer_id = google_account.customer_id

            # Final check — nowhere to get customer_id from
            if not customer_id:
                return Response(
                    {
                        "success": False,
                        "error": "Google Ads customer_id not found. Please reconnect your Google Ads account.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Attempt to get tokens from DB
            refresh_token = google_account.user_token if google_account else None
            access_token  = google_account.access_token if google_account else None

            # Fallback to settings.py (from .env) if DB is empty
            if not refresh_token:
                refresh_token = getattr(settings, "GOOGLE_REFRESH_TOKEN", None)

            if not access_token:
                access_token = getattr(settings, "GOOGLE_ACCESS_TOKEN", None)

            # Strict check: If no refresh token exists in either place, stop here.
            if not refresh_token:
                return Response(
                    {
                        "success": False,
                        "error": "Google refresh token missing. Please connect via OAuth or update .env",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ----------------------------------------------------------
            # 3. Build payload for Zapier
            # ----------------------------------------------------------
            campaign_name = data["campaign_name"]

            # Look into nested platform_data first, then fall back to root level
            google_data = data.get("platform_data", {}).get("google_ads", {})
            image_url   = (
                google_data.get("image_url")
                if isinstance(google_data, dict)
                else None
            ) or data.get("image_url")

            keywords_raw = data.get("keywords", [])
            keywords_str = (
                ",".join(keywords_raw)
                if isinstance(keywords_raw, list)
                else str(keywords_raw)
            )

            zapier_payload = {
                "event":             "google_ads_campaign_created",
                "campaign_name":     campaign_name,
                "image_url":         image_url,
                "customer_id":       str(customer_id).replace("-", ""),
                "login_customer_id": getattr(settings, "GOOGLE_ADS_LOGIN_CUSTOMER_ID", ""),
                "developer_token":   settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                "client_id":         settings.GOOGLE_CLIENT_ID,
                "client_secret":     settings.GOOGLE_CLIENT_SECRET,
                "refresh_token":     refresh_token,
                "access_token":      access_token or "",
                "budget":            int(data.get("budget", 500)),
                "bidding_strategy":  data.get("bidding_strategy", "MANUAL_CPC"),
                "locations":         data.get("locations", []),
                "keywords":          keywords_str,
                "cpc_bid":           int(data.get("cpc_bid", 20)),
                "ad_group_name":     data.get("ad_group_name", f"{campaign_name} AdGroup"),
                "final_url":         data.get("final_url", "https://example.com"),
                "headline_1":        data.get("headline_1", campaign_name[:30]),
                "headline_2":        data.get("headline_2", "Learn More"),
                "headline_3":        data.get("headline_3", "Contact Us Today"),
                "description":       data.get("description", "")[:90],
                "description_2":     data.get("description_2", "Call us now or visit our website.")[:90],
            }

            logger.info(
                "[GoogleAdsView] Sending to Zapier | clinic=%s | customer_id=%s | refresh_token_source=%s",
                clinic_id,
                customer_id,
                "DB" if google_account and google_account.user_token else "Settings",
            )

            print(f"--- DEBUG: CURRENT CLIENT ID IS: {settings.GOOGLE_CLIENT_ID} ---")
            print(f"--- DEBUG: CUSTOMER ID USED: {customer_id} ---")
            print(f"--- DEBUG: ZAPIER PAYLOAD: {zapier_payload} ---")

            # ----------------------------------------------------------
            # 4. Send to Zapier — FIXED: use ZAPIER_WEBHOOK_GOOGLE_ADS_URL
            # Previously send_to_zapier_social() was called here which uses
            # ZAPIER_WEBHOOK_URL (general social webhook) — wrong Zap.
            # Now we POST directly to the dedicated Google Ads webhook URL.
            # ----------------------------------------------------------
            webhook_url = settings.ZAPIER_WEBHOOK_GOOGLE_ADS_URL
            try:
                zapier_resp = requests.post(webhook_url, json=zapier_payload, timeout=10)
                response_code = zapier_resp.status_code
                logger.info(
                    "[GoogleAdsView] Zapier response: %s | body: %s",
                    response_code, zapier_resp.text
                )
            except requests.exceptions.RequestException as e:
                logger.error("[GoogleAdsView] Zapier request failed: %s", str(e))
                return Response(
                    {"success": False, "error": "Failed to reach Zapier webhook"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            if response_code == 200:
                return Response(
                    {
                        "success": True,
                        "message": "Google Ads campaign request sent to Zapier successfully",
                        "data": {
                            "campaign_name": campaign_name,
                            "customer_id":   customer_id,
                            "has_image":     bool(image_url),
                            "status":        "sent_to_zapier",
                        },
                    },
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(
                    {
                        "success": False,
                        "error": f"Zapier webhook failed with status {response_code}",
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        except Exception:
            logger.error("[GoogleAdsView] Unexpected error:\n%s", traceback.format_exc())
            return Response(
                {"success": False, "error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )