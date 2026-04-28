import logging
import traceback
import requests
import base64

from django.conf import settings

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from restapi.models.social_account import SocialAccount

logger = logging.getLogger(__name__)


class GoogleAdsCampaignCreateAPIView(APIView):
    """
    POST /api/google-ads/create/
    Sends a Google Ads campaign creation request to Zapier
    WITH IMAGE UPLOAD (asset_id) handled in Django
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = request.data

            # ----------------------------------------------------------
            # 1. Validate required fields
            # ----------------------------------------------------------
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

            # ----------------------------------------------------------
            # 2. Load Tokens
            # ----------------------------------------------------------
            google_account = SocialAccount.objects.filter(
                clinic_id=clinic_id,
                platform="google",
                is_active=True,
            ).first()

            if not customer_id and google_account:
                customer_id = google_account.customer_id

            if not customer_id:
                return Response(
                    {"success": False, "error": "Google Ads customer_id not found"},
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
                    {"success": False, "error": "Google refresh token missing"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ----------------------------------------------------------
            # 3. Extract Data
            # ----------------------------------------------------------
            campaign_name = data["campaign_name"]

            google_data = data.get("platform_data", {}).get("google_ads", {})
            image_url = (
                google_data.get("image_url")
                if isinstance(google_data, dict)
                else None
            ) or data.get("image_url")

            keywords_raw = data.get("keywords", [])
            keywords_str = ",".join(keywords_raw) if isinstance(keywords_raw, list) else str(keywords_raw)

            # ----------------------------------------------------------
            # 4. 🔥 Upload Image → Get asset_id (NEW)
            # ----------------------------------------------------------
            asset_id = None

            if image_url:
                try:
                    # Step 1: Get fresh access token
                    auth_res = requests.post(
                        "https://oauth2.googleapis.com/token",
                        data={
                            "client_id": settings.GOOGLE_CLIENT_ID,
                            "client_secret": settings.GOOGLE_CLIENT_SECRET,
                            "refresh_token": refresh_token,
                            "grant_type": "refresh_token",
                        },
                        timeout=10,
                    )
                    auth_json = auth_res.json()

                    access_token = auth_json.get("access_token")

                    if access_token:
                        headers = {
                            "Authorization": f"Bearer {access_token}",
                            "developer-token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                            "Content-Type": "application/json",
                        }

                        cust_id  = str(customer_id).replace("-", "")
                        login_id = str(getattr(settings, "GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")).replace("-", "")

                        if login_id and login_id != cust_id:
                            headers["login-customer-id"] = login_id

                        # Download image
                        img_bytes = requests.get(image_url, timeout=15).content
                        img_b64 = base64.b64encode(img_bytes).decode("utf-8")

                        # Upload to Google Ads
                        upload_res = requests.post(
                            f"https://googleads.googleapis.com/v20/customers/{cust_id}/assets:mutate",
                            headers=headers,
                            json={
                                "operations": [{
                                    "create": {
                                        "type": "IMAGE",
                                        "name": "Campaign Image",
                                        "image_asset": {"data": img_b64}
                                    }
                                }]
                            },
                            timeout=15,
                        )

                        upload_json = upload_res.json()

                        if "results" in upload_json:
                            asset_id = upload_json["results"][0]["resourceName"]
                            logger.info(f"[ImageUpload] Asset created: {asset_id}")
                        else:
                            logger.error(f"[ImageUpload] Failed: {upload_json}")

                except Exception as e:
                    logger.error(f"[ImageUpload] Exception: {str(e)}")

            # ----------------------------------------------------------
            # 5. Build Zapier Payload
            # ----------------------------------------------------------
            zapier_payload = {
                "event": "google_ads_campaign_created",
                "campaign_name": campaign_name,

                # 🔥 IMPORTANT CHANGE
                "asset_id": asset_id,

                "customer_id": str(customer_id).replace("-", ""),
                "login_customer_id": getattr(settings, "GOOGLE_ADS_LOGIN_CUSTOMER_ID", ""),
                "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "access_token": access_token or "",
                "budget": int(data.get("budget", 500)),
                "bidding_strategy": data.get("bidding_strategy", "MANUAL_CPC"),
                "locations": data.get("locations", []),
                "keywords": keywords_str,
                "cpc_bid": int(data.get("cpc_bid", 20)),
                "ad_group_name": data.get("ad_group_name", f"{campaign_name} AdGroup"),
                "final_url": data.get("final_url", "https://example.com"),
                "headline_1": data.get("headline_1", campaign_name[:30]),
                "headline_2": data.get("headline_2", "Learn More"),
                "headline_3": data.get("headline_3", "Contact Us Today"),
                "description": data.get("description", "")[:90],
                "description_2": data.get("description_2", "Call us now")[:90],
            }

            # ----------------------------------------------------------
            # 6. Send to Zapier
            # ----------------------------------------------------------
            webhook_url = settings.ZAPIER_WEBHOOK_GOOGLE_ADS_URL

            zapier_resp = requests.post(webhook_url, json=zapier_payload, timeout=10)

            if zapier_resp.status_code == 200:
                return Response(
                    {
                        "success": True,
                        "message": "Sent to Zapier",
                        "asset_id": asset_id,
                    },
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(
                    {
                        "success": False,
                        "error": zapier_resp.text,
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        except Exception:
            logger.error("[GoogleAdsView] Error:\n%s", traceback.format_exc())
            return Response(
                {"success": False, "error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )