import logging
import traceback
import requests

from django.conf import settings

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from restapi.models import Campaign
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

            clinic_id   = data.get("clinic_id")
            customer_id = data.get("customer_id")

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

            google_account = SocialAccount.objects.filter(
                clinic_id=clinic_id,
                platform="google",
                is_active=True,
            ).first()

            if not customer_id and google_account:
                customer_id = google_account.customer_id

            if not customer_id:
                return Response(
                    {
                        "success": False,
                        "error": "Google Ads customer_id not found. Please reconnect your Google Ads account.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            refresh_token = google_account.user_token if google_account else None
            access_token  = google_account.access_token if google_account else None

            if not refresh_token:
                refresh_token = getattr(settings, "GOOGLE_REFRESH_TOKEN", None)

            if not access_token:
                access_token = getattr(settings, "GOOGLE_ACCESS_TOKEN", None)

            if not refresh_token:
                return Response(
                    {
                        "success": False,
                        "error": "Google refresh token missing. Please connect via OAuth or update .env",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            campaign_name = data["campaign_name"]

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


class GoogleAdsCampaignStatusAPIView(APIView):
    """
    POST /api/google-ads/status/
    Pause or enable a Google Ads campaign directly via Google Ads REST API.
    Called when user clicks pause/stop in the UI.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            campaign_id = request.data.get("campaign_id")
            action      = request.data.get("action")  # "pause" or "enable"

            if not campaign_id or action not in ["pause", "enable"]:
                return Response(
                    {"error": "campaign_id and action (pause/enable) are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            campaign  = Campaign.objects.get(id=campaign_id)
            clinic_id = campaign.clinic_id

            google_account = SocialAccount.objects.filter(
                clinic_id=clinic_id,
                platform="google",
                is_active=True,
            ).first()

            if not google_account:
                return Response(
                    {"error": "Google Ads not connected for this clinic"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            cust_id = str(google_account.customer_id or "").replace("-", "")
            if not cust_id:
                return Response(
                    {"error": "Google Ads customer_id missing. Please reconnect."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            refresh_token = google_account.user_token
            if not refresh_token:
                refresh_token = getattr(settings, "GOOGLE_REFRESH_TOKEN", None)

            if not refresh_token:
                return Response(
                    {"error": "Google refresh token missing. Please reconnect."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Step 1: Get fresh access token
            auth_res = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id":     settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type":    "refresh_token",
                },
                timeout=10,
            )
            auth_json = auth_res.json()

            if "access_token" not in auth_json:
                logger.error("[GoogleAdsStatus] Token refresh failed: %s", auth_json)
                return Response(
                    {"error": "Failed to refresh Google token"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            access_token = auth_json["access_token"]

            # Step 2: Build headers
            headers = {
                "Authorization":   f"Bearer {access_token}",
                "developer-token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                "Content-Type":    "application/json",
            }

            login_id = str(getattr(settings, "GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")).replace("-", "")
            if login_id and login_id != cust_id:
                headers["login-customer-id"] = login_id

            # Step 3: Find campaign_resource_name from platform_data
            platform_data          = campaign.platform_data or {}
            google_data            = platform_data.get("google_ads", {})
            campaign_resource_name = None

            if isinstance(google_data, dict):
                campaign_resource_name = google_data.get("campaign_resource_name")

            # Step 4: If not stored, search by campaign name
            if not campaign_resource_name:
                safe_name = campaign.campaign_name.strip().replace("'", "\\'")
                query = (
                    f"SELECT campaign.id, campaign.name, campaign.resource_name "
                    f"FROM campaign "
                    f"WHERE campaign.name LIKE '%{safe_name}%' "
                    f"AND campaign.status != 'REMOVED' "
                    f"LIMIT 5"
                )
                logger.info(
                    "[GoogleAdsStatus] Searching by name: %s | cust_id: %s",
                    safe_name, cust_id,
                )

                search_resp = requests.post(
                    f"https://googleads.googleapis.com/v17/customers/{cust_id}/googleAds:search",
                    headers=headers,
                    json={"query": query},
                    timeout=10,
                )
                try:
                    search_res = search_resp.json() if search_resp.text.strip() else {}
                except Exception as e:
                    logger.error("[GoogleAdsStatus] Failed to parse search response: %s", e)
                    search_res = {}

                results = search_res.get("results", [])
                if results:
                    campaign_resource_name = results[0].get("campaign", {}).get("resourceName")
                    logger.info("[GoogleAdsStatus] Found resource_name: %s", campaign_resource_name)

                    updated_platform_data = campaign.platform_data or {}
                    if not isinstance(updated_platform_data.get("google_ads"), dict):
                        updated_platform_data["google_ads"] = {}
                    updated_platform_data["google_ads"]["campaign_resource_name"] = campaign_resource_name
                    campaign.platform_data = updated_platform_data
                    campaign.save(update_fields=["platform_data"])
                else:
                    logger.error(
                        "[GoogleAdsStatus] No campaign found for name: %s | http_status: %s | response: %s",
                        safe_name, search_resp.status_code, search_res,
                    )

            if not campaign_resource_name:
                logger.info(
                    "[GoogleAdsStatus] No Google Ads campaign found for '%s' — skipping",
                    campaign.campaign_name,
                )
                return Response(
                    {
                        "success": True,
                        "skipped": True,
                        "message": "No Google Ads campaign found — skipped",
                    },
                    status=status.HTTP_200_OK,
                )

            # Step 5: Mutate campaign status
            new_status = "PAUSED" if action == "pause" else "ENABLED"

            mutate_resp = requests.post(
                f"https://googleads.googleapis.com/v17/customers/{cust_id}/campaigns:mutate",
                headers=headers,
                json={
                    "operations": [
                        {
                            "update": {
                                "resourceName": campaign_resource_name,
                                "status":       new_status,
                            },
                            "updateMask": "status",
                        }
                    ]
                },
                timeout=10,
            )
            try:
                mutate_res = mutate_resp.json() if mutate_resp.text.strip() else {}
            except Exception as e:
                logger.error("[GoogleAdsStatus] Failed to parse mutate response: %s", e)
                mutate_res = {}

            if "results" not in mutate_res:
                logger.error("[GoogleAdsStatus] Mutate failed: %s", mutate_res)
                return Response(
                    {
                        "error":   "Failed to update Google Ads campaign status",
                        "details": mutate_res,
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            logger.info(
                "[GoogleAdsStatus] Campaign %s set to %s",
                campaign_resource_name, new_status,
            )

            return Response(
                {
                    "success":    True,
                    "campaign_id": str(campaign_id),
                    "action":     action,
                    "new_status": new_status,
                },
                status=status.HTTP_200_OK,
            )

        except Campaign.DoesNotExist:
            return Response(
                {"error": "Campaign not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error("[GoogleAdsStatus] Unexpected error:\n%s", traceback.format_exc())
            return Response(
                {"success": False, "error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )